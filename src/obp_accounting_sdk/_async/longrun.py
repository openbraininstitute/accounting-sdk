"""Longrun session."""

import logging
from dataclasses import dataclass
from http import HTTPStatus
from types import TracebackType
from typing import Any, Self
from uuid import UUID

import httpx

from obp_accounting_sdk.constants import (
    HEARTBEAT_INTERVAL,
    MAX_JOB_NAME_LENGTH,
    LongrunStatus,
    ServiceSubtype,
    ServiceType,
)
from obp_accounting_sdk.errors import (
    AccountingCancellationError,
    AccountingReservationError,
    AccountingUsageError,
    InsufficientFundsError,
)
from obp_accounting_sdk.utils import create_async_periodic_task_manager, get_current_timestamp

L = logging.getLogger(__name__)


@dataclass
class LongRunJobInfo:
    service_subtype: ServiceSubtype | str
    proj_id: UUID
    user_id: UUID
    name: str | None
    duration: int
    instances: int
    instance_type: str


async def make_reservation(
    base_url: str,
    http_client: httpx.AsyncClient,
    job_info: LongRunJobInfo,
) -> UUID:
    """Make a new reservation."""
    data = {
        "type": ServiceType.LONGRUN,
        "subtype": job_info.service_subtype,
        "proj_id": str(job_info.proj_id),
        "user_id": str(job_info.user_id),
        "name": job_info.name,
        "duration": job_info.duration,
        "instances": job_info.instances,
        "instance_type": job_info.instance_type,
    }
    try:
        response = await http_client.post(
            f"{base_url}/reservation/longrun",
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
        job_id = UUID(response.json()["data"]["job_id"])
    except Exception as exc:
        errmsg = "Error while parsing the response"
        raise AccountingReservationError(message=errmsg) from exc
    return job_id


async def _send_status(
    base_url: str,
    http_client: httpx.AsyncClient,
    job_info: LongRunJobInfo,
    job_id: UUID,
    status: LongrunStatus,
) -> None:
    data = {
        "type": ServiceType.LONGRUN,
        "name": job_info.name,
        "subtype": job_info.service_subtype,
        "job_id": str(job_id),
        "proj_id": str(job_info.proj_id),
        "instances": str(job_info.instances),
        "instance_type": job_info.instance_type,
        "status": status,
        "timestamp": get_current_timestamp(),
    }
    try:
        response = await http_client.post(f"{base_url}/usage/longrun", json=data)
        response.raise_for_status()
    except httpx.RequestError as exc:
        errmsg = f"Error in request {exc.request.method} {exc.request.url}"
        raise AccountingUsageError(message=errmsg) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        errmsg = f"Error in response to {exc.request.method} {exc.request.url}: {status_code}"
        raise AccountingUsageError(message=errmsg, http_status_code=status_code) from exc


async def start(
    base_url: str, http_client: httpx.AsyncClient, job_info: LongRunJobInfo, job_id: UUID
) -> None:
    """Start accounting for the current job."""
    return await _send_status(
        base_url=base_url,
        http_client=http_client,
        job_info=job_info,
        job_id=job_id,
        status=LongrunStatus.STARTED,
    )


async def finish(
    base_url: str, http_client: httpx.AsyncClient, job_info: LongRunJobInfo, job_id: UUID
) -> None:
    """Send a session closure event to accounting."""
    return await _send_status(
        base_url=base_url,
        http_client=http_client,
        job_info=job_info,
        job_id=job_id,
        status=LongrunStatus.FINISHED,
    )


async def cancel_reservation(
    base_url: str,
    http_client: httpx.AsyncClient,
    job_id: UUID,
) -> None:
    """Cancel the reservation."""
    try:
        response = await http_client.delete(f"{base_url}/reservation/longrun/{job_id}")
        response.raise_for_status()
    except httpx.RequestError as exc:
        errmsg = f"Error in request {exc.request.method} {exc.request.url}"
        raise AccountingCancellationError(message=errmsg) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        errmsg = f"Error in response to {exc.request.method} {exc.request.url}: {status_code}"
        raise AccountingCancellationError(message=errmsg, http_status_code=status_code) from exc


async def send_heartbeat(
    base_url: str, http_client: httpx.AsyncClient, job_info: LongRunJobInfo, job_id: UUID
) -> None:
    """Send heartbeat event to accounting."""
    return await _send_status(
        base_url=base_url,
        http_client=http_client,
        job_info=job_info,
        job_id=job_id,
        status=LongrunStatus.RUNNING,
    )


class AsyncLongrunSession:
    """Longrun Session."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
        subtype: ServiceSubtype | str,
        proj_id: UUID | str,
        user_id: UUID | str,
        instances: int,
        instance_type: str,
        duration: int,
        name: str | None = None,
        job_id: UUID | None = None,
    ) -> None:
        """Initialization."""
        self._http_client = http_client
        self._base_url: str = base_url
        self._job_info = LongRunJobInfo(
            service_subtype=ServiceSubtype(subtype),
            proj_id=UUID(str(proj_id)),
            user_id=UUID(str(user_id)),
            name=name,
            duration=duration,
            instances=instances,
            instance_type=instance_type,
        )
        self._job_id: UUID | None = job_id
        self._job_running: bool = False
        self._cancel_heartbeat_sender: Any | None = None

    @property
    def job_id(self) -> UUID | None:
        """Return the job id."""
        return self._job_id

    @property
    def name(self) -> str | None:
        """Return the job name."""
        return self._job_info.name

    @name.setter
    def name(self, value: str) -> None:
        """Set the job name."""
        if not isinstance(value, str) or len(value) > MAX_JOB_NAME_LENGTH:
            errmsg = f"Job name must be a string with max length {MAX_JOB_NAME_LENGTH}"
            raise ValueError(errmsg)
        if self._job_info.name is not None and self._job_info.name != value:
            L.info("Overriding previous name value '%s' with '%s'", self.name, value)
        self._job_info.name = value

    async def make_reservation(self) -> None:
        """Make a new reservation."""
        if self._job_id is not None:
            errmsg = "Cannot make a reservation more than once"
            raise RuntimeError(errmsg)
        self._job_id = await make_reservation(
            base_url=self._base_url,
            http_client=self._http_client,
            job_info=self._job_info,
        )

    async def start(self) -> None:
        """Start accounting for the current job."""
        if self._job_id is None:
            errmsg = "Cannot send session before making a successful reservation"
            raise RuntimeError(errmsg)
        await start(
            base_url=self._base_url,
            http_client=self._http_client,
            job_info=self._job_info,
            job_id=self._job_id,
        )
        self._cancel_heartbeat_sender = create_async_periodic_task_manager(
            self._send_heartbeat, HEARTBEAT_INTERVAL
        )
        self._job_running = True

    async def cancel_reservation(self) -> None:
        """Cancel the reservation."""
        if self._job_id is None:
            errmsg = "Cannot cancel a reservation without a job id"
            raise RuntimeError(errmsg)
        await cancel_reservation(
            base_url=self._base_url,
            http_client=self._http_client,
            job_id=self._job_id,
        )

    async def _finish(self) -> None:
        """Send a session closure event to accounting."""
        assert self._job_id is not None  # noqa: S101
        await finish(
            base_url=self._base_url,
            http_client=self._http_client,
            job_info=self._job_info,
            job_id=self._job_id,
        )

    async def _send_heartbeat(self) -> None:
        """Send heartbeat event to accounting."""
        if self._job_id is None:
            errmsg = "Cannot send heartbeat before making a successful reservation"
            raise RuntimeError(errmsg)
        await send_heartbeat(
            base_url=self._base_url,
            http_client=self._http_client,
            job_info=self._job_info,
            job_id=self._job_id,
        )

    async def __aenter__(self) -> Self:
        """Initialize when entering the context manager."""
        if self._job_id is None:
            await self.make_reservation()
        return self

    async def finish(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        _exc_tb: TracebackType | None = None,
    ) -> None:
        """Cleanup when exiting the context manager."""
        if self._cancel_heartbeat_sender:
            self._cancel_heartbeat_sender()

        if self._job_id is None and not exc_val:
            errmsg = "Cannot close session before making a successful reservation"
            raise RuntimeError(errmsg)

        if not self._job_running and exc_type:
            L.warning(f"Unhandled application error {exc_type.__name__}, cancelling reservation")
            try:
                await self.cancel_reservation()
            except AccountingCancellationError as ex:
                L.warning("Error while cancelling the reservation: %r", ex)

        elif not self._job_running and not exc_val:
            errmsg = "Accounting session must be started before closing."
            raise RuntimeError(errmsg)

        elif self._job_running and exc_type:
            # TODO: Consider refunding the user
            try:
                await self._finish()
            except AccountingUsageError as ex:
                L.error("Error while finishing the job: %r", ex)

        else:
            try:
                L.debug("Finishing the job")
                await self._finish()
            except AccountingUsageError as ex:
                L.error("Error while finishing the job: %r", ex)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        await self.finish(exc_type, exc_val, _exc_tb)


class AsyncNullLongrunSession:
    """Null session that can be used to do nothing."""

    def __init__(self) -> None:
        """Initialization."""
        self.instances = 0

    async def __aenter__(self) -> Self:
        """Initialize when entering the context manager."""
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        """Cleanup when exiting the context manager."""

    async def make_reservation(self) -> None:
        """Make a reservation for the current job."""

    async def start(self) -> None:
        """Start accounting for the current job."""

    async def finish(self) -> None:
        """Finalize accounting session for the current job."""
