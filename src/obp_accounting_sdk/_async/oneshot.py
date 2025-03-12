"""Oneshot session."""

import logging
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


class AsyncOneshotSession:
    """Oneshot Session."""

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
        """Initialization."""
        self._http_client = http_client
        self._base_url: str = base_url
        self._service_type: ServiceType = ServiceType.ONESHOT
        self._service_subtype: ServiceSubtype = ServiceSubtype(subtype)
        self._proj_id: UUID = UUID(str(proj_id))
        self._user_id: UUID = UUID(str(user_id))
        self._name = name
        self._job_id: UUID | None = None
        self._count = self.count = count

    @property
    def count(self) -> int:
        """Return the count value used for reservation or usage."""
        return self._count

    @count.setter
    def count(self, value: int) -> None:
        """Set the count to be used for usage."""
        if not isinstance(value, int) or value < 0:
            errmsg = "count must be an integer >= 0"
            raise ValueError(errmsg)
        if self.count is not None and self.count != value:
            L.info("Overriding previous count value %s with %s", self.count, value)
        self._count = value

    @property
    def name(self) -> str | None:
        """Return the job name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the job name."""
        if not isinstance(value, str) or len(value) > MAX_JOB_NAME_LENGTH:
            errmsg = f"Job name must be a string with max length {MAX_JOB_NAME_LENGTH}"
            raise ValueError(errmsg)
        if self.name is not None and self.name != value:
            L.info("Overriding previous name value '%s' with '%s'", self.name, value)
        self._name = value

    async def _make_reservation(self) -> None:
        """Make a new reservation."""
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

    async def _cancel_reservation(self) -> None:
        """Cancel the reservation."""
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

    async def __aenter__(self) -> Self:
        """Initialize when entering the context manager."""
        await self._make_reservation()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Cleanup when exiting the context manager."""
        if exc_type is None:
            await self._send_usage()
        else:
            L.warning(f"Unhandled application error {exc_type.__name__}, cancelling reservation")
            try:
                await self._cancel_reservation()
            except AccountingCancellationError as ex:
                L.warning("Error while cancelling the reservation: %r", ex)


class AsyncNullOneshotSession:
    """Null session that can be used to do nothing."""

    def __init__(self) -> None:
        """Initialization."""
        self.count = 0

    async def __aenter__(self) -> Self:
        """Initialize when entering the context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Cleanup when exiting the context manager."""
