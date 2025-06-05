"""Longrun session."""

import logging
import platform
import signal
import time
from http import HTTPStatus
from multiprocessing import get_context
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self
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
from obp_accounting_sdk.utils import get_current_timestamp

if TYPE_CHECKING:
    from multiprocessing.process import BaseProcess

L = logging.getLogger(__name__)


class SyncLongrunSession:
    """Longrun Session."""

    def __init__(
        self,
        http_client: httpx.Client,
        base_url: str,
        subtype: ServiceSubtype | str,
        proj_id: UUID | str,
        user_id: UUID | str,
        instances: int,
        instance_type: str,
        duration: int,
        name: str | None = None,
    ) -> None:
        """Initialization."""
        self._http_client = http_client
        self._base_url: str = base_url
        self._service_type: ServiceType = ServiceType.LONGRUN
        self._service_subtype: ServiceSubtype = ServiceSubtype(subtype)
        self._proj_id: UUID = UUID(str(proj_id))
        self._user_id: UUID = UUID(str(user_id))
        self._job_id: UUID | None = None
        self._name = name
        self._job_running: bool = False
        self._instances: int = instances
        self._instance_type: str = instance_type
        self._duration: int = duration
        self._heartbeat_sender_process: BaseProcess | None = None

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

    def _make_reservation(self) -> None:
        """Make a new reservation."""
        if self._job_id is not None:
            errmsg = "Cannot make a reservation more than once"
            raise RuntimeError(errmsg)
        data = {
            "type": self._service_type,
            "subtype": self._service_subtype,
            "proj_id": str(self._proj_id),
            "user_id": str(self._user_id),
            "name": self.name,
            "duration": self._duration,
            "instances": self._instances,
            "instance_type": self._instance_type,
        }
        try:
            response = self._http_client.post(
                f"{self._base_url}/reservation/longrun",
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

    def _cancel_reservation(self) -> None:
        """Cancel the reservation."""
        if self._job_id is None:
            errmsg = "Cannot cancel a reservation without a job id"
            raise RuntimeError(errmsg)
        try:
            response = self._http_client.delete(
                f"{self._base_url}/reservation/longrun/{self._job_id}"
            )
            response.raise_for_status()
        except httpx.RequestError as exc:
            errmsg = f"Error in request {exc.request.method} {exc.request.url}"
            raise AccountingCancellationError(message=errmsg) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            errmsg = f"Error in response to {exc.request.method} {exc.request.url}: {status_code}"
            raise AccountingCancellationError(message=errmsg, http_status_code=status_code) from exc

    def _finish(self) -> None:
        """Send a session closure event to accounting."""
        if self._job_id is None:
            errmsg = "Cannot close session before making a successful reservation"
            raise RuntimeError(errmsg)
        data = {
            "type": self._service_type,
            "subtype": self._service_subtype,
            "proj_id": str(self._proj_id),
            "job_id": str(self._job_id),
            "name": self.name,
            "status": LongrunStatus.FINISHED,
            "instances": str(self._instances),
            "instance_type": self._instance_type,
            "timestamp": get_current_timestamp(),
        }
        try:
            response = self._http_client.post(f"{self._base_url}/usage/longrun", json=data)
            response.raise_for_status()
        except httpx.RequestError as exc:
            errmsg = f"Error in request {exc.request.method} {exc.request.url}"
            raise AccountingUsageError(message=errmsg) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            errmsg = f"Error in response to {exc.request.method} {exc.request.url}: {status_code}"
            raise AccountingUsageError(message=errmsg, http_status_code=status_code) from exc

    def _send_heartbeat(self, http_sync_client: httpx.Client) -> None:
        """Send heartbeat event to accounting."""
        if self._job_id is None:
            errmsg = "Cannot send heartbeat before making a successful reservation"
            raise RuntimeError(errmsg)
        data = {
            "type": self._service_type,
            "subtype": self._service_subtype,
            "job_id": str(self._job_id),
            "proj_id": str(self._proj_id),
            "status": LongrunStatus.RUNNING,
            "instances": str(self._instances),
            "instance_type": self._instance_type,
            "timestamp": get_current_timestamp(),
        }
        try:
            response = http_sync_client.post(f"{self._base_url}/usage/longrun", json=data)
            response.raise_for_status()
        except httpx.RequestError as exc:
            errmsg = f"Error in request {exc.request.method} {exc.request.url}"
            raise AccountingUsageError(message=errmsg) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            errmsg = f"Error in response to {exc.request.method} {exc.request.url}: {status_code}"
            raise AccountingUsageError(message=errmsg, http_status_code=status_code) from exc

    def _heartbeat_sender_loop(self) -> None:
        """Periodically send a signal to the accounting service that the job is still alive."""
        running = True

        def signal_handler(_signum: int, _frame: Any) -> None:
            nonlocal running
            running = False

        signal.signal(signal.SIGTERM, signal_handler)

        with httpx.Client() as http_sync_client:
            while running:
                try:
                    time.sleep(HEARTBEAT_INTERVAL)
                    self._send_heartbeat(http_sync_client)
                except RuntimeError as exc:
                    L.error("Error in heartbeat sender: %s", exc)

    def start(self) -> None:
        """Start accounting for the current job."""
        if self._job_id is None:
            errmsg = "Cannot send session before making a successful reservation"
            raise RuntimeError(errmsg)
        data = {
            "type": self._service_type,
            "subtype": self._service_subtype,
            "job_id": str(self._job_id),
            "proj_id": str(self._proj_id),
            "status": LongrunStatus.STARTED,
            "instances": str(self._instances),
            "instance_type": "fargate",
            "timestamp": get_current_timestamp(),
        }
        try:
            response = self._http_client.post(f"{self._base_url}/usage/longrun", json=data)
            response.raise_for_status()
        except httpx.RequestError as exc:
            errmsg = f"Error in request {exc.request.method} {exc.request.url}"
            raise AccountingUsageError(message=errmsg) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            errmsg = f"Error in response to {exc.request.method} {exc.request.url}: {status_code}"
            raise AccountingUsageError(message=errmsg, http_status_code=status_code) from exc

        # For some reason child process is hanging when using default spawn method on MacOS.
        # TODO: investigate further and remove this workaround.
        ctx = get_context("fork") if platform.system() != "Linux" else get_context()

        self._heartbeat_sender_process = ctx.Process(
            target=self._heartbeat_sender_loop,
            daemon=True,
        )
        self._heartbeat_sender_process.start()
        self._job_running = True

    def __enter__(self) -> Self:
        """Initialize when entering the context manager."""
        self._make_reservation()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Cleanup when exiting the context manager."""
        if self._heartbeat_sender_process:
            self._heartbeat_sender_process.terminate()
            self._heartbeat_sender_process.join()

        if not self._job_running and exc_type:
            L.warning(f"Unhandled application error {exc_type.__name__}, cancelling reservation")
            try:
                self._cancel_reservation()
            except AccountingCancellationError as ex:
                L.warning("Error while cancelling the reservation: %r", ex)

        elif not self._job_running and not exc_val:
            errmsg = "Accounting session must be started before closing."
            raise RuntimeError(errmsg)

        elif self._job_running and exc_type:
            # TODO: Consider refunding the user
            try:
                self._finish()
            except AccountingUsageError as ex:
                L.error("Error while finishing the job: %r", ex)

        else:
            try:
                L.debug("Finishing the job")
                self._finish()
            except AccountingUsageError as ex:
                L.error("Error while finishing the job: %r", ex)


class SyncNullLongrunSession:
    """Null session that can be used to do nothing."""

    def __init__(self) -> None:
        """Initialization."""
        self.instances = 0

    def __enter__(self) -> Self:
        """Initialize when entering the context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Cleanup when exiting the context manager."""

    def start(self) -> None:
        """Start accounting for the current job."""
