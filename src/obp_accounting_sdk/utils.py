"""Common utilities."""

import asyncio
import logging
import platform
import time
from collections.abc import Callable, Coroutine
from multiprocessing import get_context
from typing import Any

from obp_accounting_sdk.constants import HEARTBEAT_INTERVAL

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


def create_async_periodic_task_manager(callback: Callable[[], Any]) -> Callable[[], None]:
    """Create a periodic task manager that periodically calls the callback.

    Args:
        callback: The callback function to call periodically.

    Returns:
        A callable that cancels the heartbeat when called.
    """

    async def heartbeat_loop() -> None:
        """Async heartbeat loop."""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await callback()
            except RuntimeError as exc:
                L.error("Error in heartbeat sender: %s", exc)
            except asyncio.CancelledError:
                L.debug("Heartbeat sender loop cancelled")
                break

    return create_cancellable_async_task(heartbeat_loop())


def create_sync_periodic_task_manager(callback: Callable[[], None]) -> Callable[[], None]:
    """Create a synchronous heartbeat manager that periodically calls the callback.

    Args:
        callback: The callback function to call periodically.

    Returns:
        A callable that cancels the heartbeat when called.
    """

    def heartbeat_loop() -> None:
        """Sync heartbeat loop."""
        while True:
            try:
                time.sleep(HEARTBEAT_INTERVAL)
                callback()
            except RuntimeError as exc:
                L.error("Error in heartbeat sender: %s", exc)
            except Exception as exc:
                L.error("Error in heartbeat sender: %s", exc)
                break

    return create_cancellable_sync_task(heartbeat_loop)
