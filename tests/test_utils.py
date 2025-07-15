import asyncio
import multiprocessing
import time
from unittest.mock import patch

import pytest

from obp_accounting_sdk.utils import (
    create_async_periodic_task_manager,
    create_sync_periodic_task_manager,
    get_current_timestamp,
)


def test_get_current_timestamp():
    """Test get_current_timestamp returns current time as string."""
    with patch("time.time", return_value=1234567890):
        assert get_current_timestamp() == "1234567890"


class TestAsyncPeriodicTaskManager:
    @staticmethod
    @pytest.mark.asyncio
    async def test_async_periodic_task_manager_basic():
        """Test basic functionality of async periodic task manager."""
        call_count = 0

        async def callback():
            nonlocal call_count
            call_count += 1

        cancel_task = create_async_periodic_task_manager(callback, 0.1)

        # Let it run for a bit
        await asyncio.sleep(0.25)

        # Cancel the task
        cancel_task()

        # Should have been called at least 2 times
        assert call_count >= 2

    @staticmethod
    @pytest.mark.asyncio
    async def test_async_periodic_task_manager_cancellation():
        """Test that cancelling stops the task."""
        call_count = 0

        async def callback():
            nonlocal call_count
            call_count += 1

        cancel_task = create_async_periodic_task_manager(callback, 0.1)

        # Let it run for a bit
        await asyncio.sleep(0.15)
        initial_count = call_count

        # Cancel the task
        cancel_task()

        # Wait a bit more
        await asyncio.sleep(0.15)

        # Count should not have increased significantly after cancellation
        assert call_count <= initial_count + 1

    @staticmethod
    @pytest.mark.asyncio
    async def test_async_periodic_task_manager_exception_handling():
        """Test that exceptions in callback are handled gracefully."""
        call_count = 0

        async def callback():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                error_msg = "Test error"
                raise RuntimeError(error_msg)

        with patch("obp_accounting_sdk.utils.L.error") as mock_logger:
            cancel_task = create_async_periodic_task_manager(callback, 0.1)

            # Let it run for a bit
            await asyncio.sleep(0.25)

            # Cancel the task
            cancel_task()

            # Should have logged the error
            mock_logger.assert_called_once()
            assert "Error in callback" in str(mock_logger.call_args)

    @staticmethod
    @pytest.mark.asyncio
    async def test_async_periodic_task_manager_cancelled_error():
        """Test that CancelledError is handled gracefully."""
        call_count = 0

        async def callback():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise asyncio.CancelledError

        with patch("obp_accounting_sdk.utils.L.debug") as mock_logger:
            cancel_task = create_async_periodic_task_manager(callback, 0.1)

            # Let it run for a bit
            await asyncio.sleep(0.25)

            # Cancel the task
            cancel_task()

            # Should have logged the cancellation
            mock_logger.assert_called_with("Task loop cancelled")


class TestSyncPeriodicTaskManager:
    @staticmethod
    def test_sync_periodic_task_manager_basic():
        """Test basic functionality of sync periodic task manager."""
        # Use a shared variable to track callback calls
        call_count = multiprocessing.Value("i", 0)

        def callback():
            with call_count.get_lock():
                call_count.value += 1

        cancel_task = create_sync_periodic_task_manager(callback, 1)

        # Let it run for a bit
        time.sleep(2.5)

        # Cancel the task
        cancel_task()

        # Should have been called at least 2 times
        assert call_count.value >= 2

    @staticmethod
    def test_sync_periodic_task_manager_cancellation():
        """Test that cancelling stops the task."""
        # Use a shared variable to track callback calls
        call_count = multiprocessing.Value("i", 0)

        def callback():
            with call_count.get_lock():
                call_count.value += 1

        cancel_task = create_sync_periodic_task_manager(callback, 1)

        # Let it run for a bit
        time.sleep(1.5)
        initial_count = call_count.value

        # Cancel the task
        cancel_task()

        # Wait a bit more
        time.sleep(1.5)

        # Count should not have increased significantly after cancellation
        assert call_count.value <= initial_count + 1

    @staticmethod
    def test_sync_periodic_task_manager_returns_cancel_function():
        """Test that the function returns a cancel function."""

        def callback():
            pass

        cancel_task = create_sync_periodic_task_manager(callback, 1)

        # Should return a callable
        assert callable(cancel_task)

        # Cancel immediately
        cancel_task()

    @staticmethod
    def test_sync_periodic_task_manager_with_shared_state():
        """Test sync periodic task manager with shared state."""
        # Test that the process is actually created and can be cancelled
        manager = multiprocessing.Manager()
        shared_list = manager.list()

        def callback():
            shared_list.append(time.time())

        cancel_task = create_sync_periodic_task_manager(callback, 1)

        # Let it run for a bit
        time.sleep(2.5)

        # Cancel the task
        cancel_task()

        # Should have some entries
        assert len(shared_list) >= 2
