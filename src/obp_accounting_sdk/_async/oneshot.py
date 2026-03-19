"""Oneshot accounting sessions for single-use jobs.

This module provides async oneshot session classes for reserving and tracking
usage of short computational jobs against the accounting service.

Two concrete implementations are available:

- ``AsyncOneshotSession``: Communicates with the accounting HTTP API to reserve
  budget, report usage, and cancel reservations.
- ``AsyncNullOneshotSession``: A no-op implementation that satisfies the same
  interface without making any HTTP calls. Useful for testing, local development,
  or when accounting is disabled.

Both classes share a common interface defined by ``AsyncBaseOneshotSession`` and
can be used as async context managers or managed manually.

Usage as a context manager:

    async with AsyncOneshotSession(
        http_client=client,
        subtype=ServiceSubtype.ML_LLM,
        proj_id="...",
        user_id="...",
        count=10,
    ) as session:
        # perform work
        session.count = actual_count  # optionally adjust before exit

On context exit, usage is automatically reported on success, or the reservation
is cancelled if an unhandled exception occurs.

Manual lifecycle management::

    session = AsyncOneshotSession(
        http_client=client,
        subtype=ServiceSubtype.ML_LLM,
        proj_id="...",
        user_id="...",
        count=10,
    )
    await session.make_reservation()
    try:
        # perform work
        session.count = actual_count  # optionally adjust before finishing
        await session.finish()
    except Exception:
        await session.cancel_reservation()
        raise
"""

import logging
from abc import ABC, abstractmethod
from http import HTTPStatus
from types import TracebackType
from typing import Self
from uuid import UUID

import httpx

from obp_accounting_sdk.constants import MAX_JOB_NAME_LENGTH, ServiceSubtype, ServiceType
from obp_accounting_sdk.errors import (
    AccountingCancellationError,
    AccountingReservationError,
    AccountingUsageError,
    InsufficientFundsError,
)
from obp_accounting_sdk.utils import get_current_timestamp

L = logging.getLogger(__name__)


class AsyncBaseOneshotSession(ABC):
    """Abstract base class defining the interface for all oneshot sessions.

    Subclasses must implement ``make_reservation``, ``start``, ``finish``, and
    ``cancel_reservation``. Common properties (``job_id``, ``count``, ``name``)
    and context manager behaviour are provided by this base class.

    This class should not be instantiated directly. Use one of the concrete
    implementations: ``AsyncOneshotSession`` or ``AsyncNullOneshotSession``.
    """

    def __init__(self, count: int, name: str | None = None) -> None:
        """Initialize shared session state.

        Args:
            count: The number of units to reserve. Must be a non-negative integer.
            name: Optional human-readable name for the job.
        """
        self._job_id: UUID | None = None
        self._finished: bool = False
        self._name = name
        self._count = self.count = count

    @property
    def job_id(self) -> UUID | None:
        """The unique identifier assigned to this job upon reservation.

        Returns ``None`` before ``make_reservation`` is called. Read-only.
        """
        return self._job_id

    @property
    def count(self) -> int:
        """The number of units to reserve or report as usage.

        Can be updated after initialization but before ``finish`` is called,
        allowing the actual usage to differ from the initial reservation.
        """
        return self._count

    @count.setter
    def count(self, value: int) -> None:
        """Set the count value.

        Raises:
            ValueError: If set to a non-integer or negative value.
        """
        if not isinstance(value, int) or value < 0:  # pyright: ignore[reportUnnecessaryIsInstance]
            errmsg = "count must be an integer >= 0"
            raise ValueError(errmsg)
        if self._count != value:
            L.info("Overriding previous count value %s with %s", self._count, value)
        self._count = value

    @property
    def name(self) -> str | None:
        """Optional human-readable name for the job.

        Can be set at initialization or updated afterwards. Maximum length is
        defined by ``MAX_JOB_NAME_LENGTH``.
        """
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the job name.

        Raises:
            ValueError: If set to a non-string or a string exceeding the max length.
        """
        if not isinstance(value, str) or len(value) > MAX_JOB_NAME_LENGTH:  # pyright: ignore[reportUnnecessaryIsInstance]
            errmsg = f"Job name must be a string with max length {MAX_JOB_NAME_LENGTH}"
            raise ValueError(errmsg)
        if self._name is not None and self._name != value:
            L.info("Overriding previous name value '%s' with '%s'", self._name, value)
        self._name = value

    @abstractmethod
    async def make_reservation(self) -> None:
        """Reserve budget for a oneshot job.

        Must be called exactly once before ``finish`` or ``cancel_reservation``.
        After a successful call, ``job_id`` is set.

        Raises:
            RuntimeError: If called more than once.
        """

    @abstractmethod
    async def start(self) -> None:
        """Start accounting for the current job. Not used for oneshot jobs."""

    @abstractmethod
    async def finish(
        self,
        exc_type: type[BaseException] | None = None,
        _exc_val: BaseException | None = None,
        _exc_tb: TracebackType | None = None,
    ) -> None:
        """Finalize the session by reporting usage or cancelling on error.

        When called without arguments (or with ``exc_type=None``), reports
        successful usage. When called with exception info (as done automatically
        by the context manager on unhandled errors), cancels the reservation.

        After a successful finish, ``cancel_reservation`` can no longer be called.

        Args:
            exc_type: The exception type if finishing due to an error, or ``None``
                for a successful finish.
            _exc_val: The exception instance (used by the context manager protocol).
            _exc_tb: The traceback (used by the context manager protocol).
        """

    @abstractmethod
    async def cancel_reservation(self) -> None:
        """Cancel the current reservation.

        Releases the reserved budget without reporting usage. Cannot be called
        after a successful ``finish``.

        Raises:
            RuntimeError: If called after ``finish`` completed successfully.
        """

    async def __aenter__(self) -> Self:
        """Initialize when entering the context manager."""
        await self.make_reservation()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Cleanup when exiting the context manager."""
        await self.finish(exc_type, exc_val, exc_tb)


class AsyncOneshotSession(AsyncBaseOneshotSession):
    """Oneshot session that communicates with the accounting HTTP API.

    Manages the full lifecycle of a oneshot job: reserving budget, reporting
    usage on success, and cancelling the reservation on failure. Can be used
    as an async context manager or managed manually.

    Args:
        http_client: An ``httpx.AsyncClient`` instance used for HTTP requests.
        base_url: Root URL of the accounting service. Typically set via
            environment variable and not customized at runtime.
        subtype: The service subtype for this job (e.g. ``ServiceSubtype.ML_LLM``).
        proj_id: The project identifier.
        user_id: The user identifier.
        count: The number of units to reserve. Can be adjusted before ``finish``.
        name: Optional human-readable name for the job.

    Raises:
        InsufficientFundsError: If the project does not have enough budget.
        AccountingReservationError: If the reservation request fails.
        AccountingUsageError: If the usage report fails.
        AccountingCancellationError: If the cancellation request fails.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
        subtype: ServiceSubtype | str,
        proj_id: UUID | str,
        user_id: UUID | str,
        count: int,
        name: str | None = None,
    ) -> None:
        super().__init__(count=count, name=name)
        self._http_client = http_client
        self._base_url: str = base_url
        self._service_type: ServiceType = ServiceType.ONESHOT
        self._service_subtype: ServiceSubtype = ServiceSubtype(subtype)
        self._proj_id: UUID = UUID(str(proj_id))
        self._user_id: UUID = UUID(str(user_id))

    async def make_reservation(self) -> None:
        """Reserve budget by calling the accounting service.

        Sends a POST request to the reservation endpoint. On success, sets
        ``job_id`` to the value returned by the service.

        Raises:
            RuntimeError: If called more than once.
            InsufficientFundsError: If the project budget is insufficient (HTTP 402).
            AccountingReservationError: On request or response errors.
        """
        if self._job_id is not None:
            errmsg = "Cannot make a reservation more than once"
            raise RuntimeError(errmsg)
        L.info("Making reservation")
        data = {
            "type": self._service_type,
            "subtype": self._service_subtype,
            "proj_id": str(self._proj_id),
            "user_id": str(self._user_id),
            "name": self.name,
            "count": str(self.count),
        }
        try:
            response = await self._http_client.post(
                f"{self._base_url}/reservation/oneshot",
                json=data,
            )
            if response.status_code == HTTPStatus.PAYMENT_REQUIRED:
                raise InsufficientFundsError
            response.raise_for_status()
        except httpx.RequestError as exc:
            errmsg = f"Error in request {exc.request.method} {exc.request.url}"
            raise AccountingReservationError(message=errmsg) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            errmsg = f"Error in response to {exc.request.method} {exc.request.url}: {status_code}"
            raise AccountingReservationError(message=errmsg, http_status_code=status_code) from exc
        try:
            self._job_id = UUID(response.json()["data"]["job_id"])
        except Exception as exc:
            errmsg = "Error while parsing the response"
            raise AccountingReservationError(message=errmsg) from exc

    async def start(self) -> None:
        """Start accounting for the current job. Not used for Oneshot jobs."""

    async def cancel_reservation(self) -> None:
        """Cancel the reservation by calling the accounting service.

        Sends a DELETE request to release the reserved budget. Cannot be called
        after a successful ``finish``.

        Raises:
            RuntimeError: If called after ``finish`` completed successfully,
                or if no reservation has been made.
            AccountingCancellationError: On request or response errors.
        """
        if self._finished:
            errmsg = "Cannot cancel a reservation after a successful finish"
            raise RuntimeError(errmsg)
        if self._job_id is None:
            errmsg = "Cannot cancel a reservation without a job id"
            raise RuntimeError(errmsg)
        L.info("Cancelling reservation for %s", self._job_id)
        try:
            response = await self._http_client.delete(
                f"{self._base_url}/reservation/oneshot/{self._job_id}"
            )
            response.raise_for_status()
        except httpx.RequestError as exc:
            errmsg = f"Error in request {exc.request.method} {exc.request.url}"
            raise AccountingCancellationError(message=errmsg) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            errmsg = f"Error in response to {exc.request.method} {exc.request.url}: {status_code}"
            raise AccountingCancellationError(message=errmsg, http_status_code=status_code) from exc

    async def _send_usage(self) -> None:
        """Send usage to accounting."""
        if self._job_id is None:
            errmsg = "Cannot send usage before making a successful reservation"
            raise RuntimeError(errmsg)
        L.info("Sending usage for %s", self._job_id)
        data = {
            "type": self._service_type,
            "subtype": self._service_subtype,
            "proj_id": str(self._proj_id),
            "name": self.name,
            "count": str(self.count),
            "job_id": str(self._job_id),
            "timestamp": get_current_timestamp(),
        }
        try:
            response = await self._http_client.post(f"{self._base_url}/usage/oneshot", json=data)
            response.raise_for_status()
        except httpx.RequestError as exc:
            errmsg = f"Error in request {exc.request.method} {exc.request.url}"
            raise AccountingUsageError(message=errmsg) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            errmsg = f"Error in response to {exc.request.method} {exc.request.url}: {status_code}"
            raise AccountingUsageError(message=errmsg, http_status_code=status_code) from exc

    async def finish(
        self,
        exc_type: type[BaseException] | None = None,
        _exc_val: BaseException | None = None,
        _exc_tb: TracebackType | None = None,
    ) -> None:
        """Finalize the session.

        If ``exc_type`` is ``None``, reports usage to the accounting service and
        marks the session as finished. If an exception type is provided, attempts
        to cancel the reservation instead (logging a warning on cancellation failure).
        """
        if exc_type is None:
            await self._send_usage()
            self._finished = True
        else:
            L.warning(f"Unhandled application error {exc_type.__name__}, cancelling reservation")
            try:
                await self.cancel_reservation()
            except AccountingCancellationError as ex:
                L.warning("Error while cancelling the reservation: %r", ex)


class AsyncNullOneshotSession(AsyncBaseOneshotSession):
    """No-op oneshot session for use when accounting is disabled.

    Implements the same interface as ``AsyncOneshotSession`` without making
    any HTTP calls. A unique ``job_id`` is auto-generated on reservation so
    that downstream code relying on ``job_id`` continues to work.

    Initializes with ``count=0`` and ``name=None``. Both can be set afterwards
    if needed.
    """

    def __init__(self) -> None:
        super().__init__(count=0)

    async def make_reservation(self) -> None:
        """Generate a local job id without contacting the accounting service.

        Raises:
            RuntimeError: If called more than once.
        """
        if self._job_id is not None:
            errmsg = "Cannot make a reservation more than once"
            raise RuntimeError(errmsg)
        self._job_id = UUID(int=0)

    async def start(self) -> None:
        """No-op. Start is not used for oneshot jobs."""

    async def finish(
        self,
        exc_type: type[BaseException] | None = None,  # noqa: ARG002
        _exc_val: BaseException | None = None,
        _exc_tb: TracebackType | None = None,
    ) -> None:
        """No-op finalization. Marks the session as finished."""
        self._finished = True

    async def cancel_reservation(self) -> None:
        """No-op cancellation."""
