"""Common utilities."""

import asyncio
import logging
import platform
import signal
import threading
import time
from collections.abc import Callable, Coroutine
from decimal import Decimal
from multiprocessing import get_context
from typing import Any
from uuid import UUID

import httpx

from obp_accounting_sdk.constants import ServiceSubtype, ServiceType
from obp_accounting_sdk.errors import AccountingReservationError

L = logging.getLogger(__name__)


def get_current_timestamp() -> str:
    """Return the current timestamp in seconds formatted as string."""
    return str(int(time.time()))


def create_cancellable_async_task(fn: Coroutine[Any, Any, Any]) -> Callable[[], Any]:
    """Create an async task that can be cancelled.

    Args:
        fn: The coroutine to run as a task.

    Returns:
        A callable that cancels the task when called.
    """
    task = asyncio.create_task(fn)
    return task.cancel


def create_cancellable_sync_task(fn: Callable[[], None]) -> Callable[[], None]:
    """Create a synchronous task that can be cancelled.

    Args:
        fn: The function to run in a separate process.

    Returns:
        A callable that terminates the process when called.
    """
    # For some reason child process is hanging when using default spawn method on MacOS.
    # TODO: investigate further and remove this workaround.
    ctx = get_context("fork") if platform.system() != "Linux" else get_context()

    process = ctx.Process(
        target=fn,
        daemon=True,
    )
    process.start()

    def cancel() -> None:
        process.terminate()
        process.join()

    return cancel


def create_async_periodic_task_manager(
    callback: Callable[[], Any], task_interval: int
) -> Callable[[], None]:
    """Create a periodic task manager that periodically calls the callback.

    Args:
        callback: The callback function to call periodically.
        task_interval: The interval in seconds between calls.

    Returns:
        A callable that cancels the task loop when called.
    """

    async def start_loop() -> None:
        """Async task loop."""
        while True:
            try:
                await asyncio.sleep(task_interval)
                await callback()
            except RuntimeError as exc:
                L.error("Error in callback: %s", exc)
            except asyncio.CancelledError:
                L.debug("Task loop cancelled")
                break

    return create_cancellable_async_task(start_loop())


def create_sync_periodic_task_manager(
    callback: Callable[[], None], task_interval: int
) -> Callable[[], None]:
    """Create a periodic task manager that periodically calls the callback.

    Args:
        callback: The callback function to call periodically.
        task_interval: The interval in seconds between calls.

    Returns:
        A callable that cancels the task loop when called.
    """

    def start_loop() -> None:
        """Sync task loop."""
        shutdown_event = threading.Event()

        def signal_handler(signum: int, _frame: Any) -> None:
            L.debug("Received signal %d, shutting down task loop gracefully", signum)
            shutdown_event.set()

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        while not shutdown_event.is_set():
            try:
                # Wait for the interval or until shutdown is requested
                if shutdown_event.wait(task_interval):
                    break
                callback()
            except RuntimeError as exc:
                L.error("Error in callback: %s", exc)
            except Exception as exc:  # noqa: BLE001
                L.error("Error in callback: %s", exc)
                break

        L.debug("Task loop exiting gracefully")

    return create_cancellable_sync_task(start_loop)


def _prepare_estimate_oneshot_cost_data(
    subtype: ServiceSubtype | str,
    count: int,
    proj_id: UUID | str,
) -> dict[str, str | int]:
    """Prepare the request data for estimate_oneshot_cost.

    Args:
        subtype: The service subtype.
        count: The count value.
        proj_id: Project ID.

    Returns:
        The prepared request data dictionary.
    """
    data: dict[str, str | int] = {
        "type": ServiceType.ONESHOT,
        "subtype": str(ServiceSubtype(subtype)),
        "count": count,
        "proj_id": str(proj_id),
    }

    return data


def _parse_estimate_oneshot_cost_response(response: httpx.Response) -> Decimal:
    """Parse the response from estimate_oneshot_cost API.

    Args:
        response: The HTTP response object.

    Returns:
        The estimated cost as a Decimal.

    Raises:
        AccountingReservationError: If the response cannot be parsed.
    """
    try:
        result = response.json()
        cost_str = result["data"]["cost"]
        return Decimal(str(cost_str))
    except Exception as exc:
        errmsg = "Error while parsing the response"
        raise AccountingReservationError(message=errmsg) from exc


def _handle_estimate_oneshot_cost_error(
    exc: httpx.RequestError | httpx.HTTPStatusError, request: httpx.Request
) -> None:
    """Handle errors from estimate_oneshot_cost API calls.

    Args:
        exc: The httpx exception that occurred.
        request: The HTTP request that failed.

    Raises:
        AccountingReservationError: Always raises with appropriate error message.
    """
    if isinstance(exc, httpx.RequestError):
        errmsg = f"Error in request {request.method} {request.url}"
        raise AccountingReservationError(message=errmsg) from exc
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        errmsg = f"Error in response to {request.method} {request.url}: {status_code}"
        raise AccountingReservationError(message=errmsg, http_status_code=status_code) from exc
