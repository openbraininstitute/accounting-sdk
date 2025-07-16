import asyncio
import multiprocessing
import signal
import threading
import time
from unittest.mock import Mock, patch

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

    @staticmethod
    def test_sync_periodic_task_manager_internal_loop_signal_handling():
        """Test signal handling in the internal loop."""
        call_count = 0

        def callback():
            nonlocal call_count
            call_count += 1

        # Mock the multiprocessing part to run the loop directly
        with patch("obp_accounting_sdk.utils.create_cancellable_sync_task") as mock_create_task:
            # Capture the start_loop function
            start_loop_func = None

            def capture_start_loop(func):
                nonlocal start_loop_func
                start_loop_func = func
                return lambda: None  # Return a dummy cancel function

            mock_create_task.side_effect = capture_start_loop

            # Create the task manager
            create_sync_periodic_task_manager(callback, 1)

            # Verify the task was created
            assert mock_create_task.called
            assert start_loop_func is not None

            # Test the signal handling by running the loop in a thread
            with patch("signal.signal") as mock_signal:
                loop_thread = threading.Thread(target=start_loop_func, daemon=True)
                loop_thread.start()

                # Give it a moment to start
                time.sleep(0.1)

                # Verify signal handlers were registered
                assert mock_signal.call_count == 2
                mock_signal.assert_any_call(signal.SIGTERM, mock_signal.call_args_list[0][0][1])
                mock_signal.assert_any_call(signal.SIGINT, mock_signal.call_args_list[1][0][1])

                # Get the signal handler
                signal_handler = mock_signal.call_args_list[0][0][1]

                # Simulate a signal
                signal_handler(signal.SIGTERM, None)

                # Wait for thread to finish
                loop_thread.join(timeout=2)

                # Thread should have finished
                assert not loop_thread.is_alive()

    @staticmethod
    def test_sync_periodic_task_manager_internal_loop_exception_handling():
        """Test exception handling in the internal loop."""
        call_count = 0

        def callback():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                error_msg = "Test error"
                raise RuntimeError(error_msg)

        # Mock the multiprocessing part to run the loop directly
        with patch("obp_accounting_sdk.utils.create_cancellable_sync_task") as mock_create_task:
            # Capture the start_loop function
            start_loop_func = None

            def capture_start_loop(func):
                nonlocal start_loop_func
                start_loop_func = func
                return lambda: None  # Return a dummy cancel function

            mock_create_task.side_effect = capture_start_loop

            # Create the task manager
            create_sync_periodic_task_manager(callback, 1)

            # Mock the logger and run the loop with a short timeout
            with (
                patch("obp_accounting_sdk.utils.L.error") as mock_error,
                patch("obp_accounting_sdk.utils.L.debug") as mock_debug,
                patch("threading.Event") as mock_event_class,
            ):
                # Create a mock event that will timeout quickly
                mock_event = Mock()
                mock_event.is_set.side_effect = [False, False, True]  # Allow 2 loops then stop
                mock_event.wait.side_effect = [False, False]  # Don't timeout, let callback run
                mock_event_class.return_value = mock_event

                # Run the loop
                start_loop_func()

                # Should have logged the error
                mock_error.assert_called_once()
                assert "Error in callback" in str(mock_error.call_args)

                # Should have logged graceful exit
                mock_debug.assert_called_with("Task loop exiting gracefully")

    @staticmethod
    def test_sync_periodic_task_manager_internal_loop_general_exception():
        """Test general exception handling breaks the loop."""
        call_count = 0

        def callback():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                error_msg = "Test error"
                raise ValueError(error_msg)

        # Mock the multiprocessing part to run the loop directly
        with patch("obp_accounting_sdk.utils.create_cancellable_sync_task") as mock_create_task:
            # Capture the start_loop function
            start_loop_func = None

            def capture_start_loop(func):
                nonlocal start_loop_func
                start_loop_func = func
                return lambda: None  # Return a dummy cancel function

            mock_create_task.side_effect = capture_start_loop

            # Create the task manager
            create_sync_periodic_task_manager(callback, 1)

            # Mock the logger and run the loop with a short timeout
            with (
                patch("obp_accounting_sdk.utils.L.error") as mock_error,
                patch("obp_accounting_sdk.utils.L.debug") as mock_debug,
                patch("threading.Event") as mock_event_class,
            ):
                # Create a mock event that will timeout quickly
                mock_event = Mock()
                mock_event.is_set.side_effect = [False, False, True]  # Allow 2 loops then stop
                mock_event.wait.side_effect = [False, False]  # Don't timeout, let callback run
                mock_event_class.return_value = mock_event

                # Run the loop
                start_loop_func()

                # Should have logged the error
                mock_error.assert_called_once()
                assert "Error in callback" in str(mock_error.call_args)

                # Should have logged graceful exit
                mock_debug.assert_called_with("Task loop exiting gracefully")

    @staticmethod
    def test_sync_periodic_task_manager_internal_loop_normal_operation():
        """Test normal operation of the internal loop."""
        call_count = 0

        def callback():
            nonlocal call_count
            call_count += 1

        # Mock the multiprocessing part to run the loop directly
        with patch("obp_accounting_sdk.utils.create_cancellable_sync_task") as mock_create_task:
            # Capture the start_loop function
            start_loop_func = None

            def capture_start_loop(func):
                nonlocal start_loop_func
                start_loop_func = func
                return lambda: None  # Return a dummy cancel function

            mock_create_task.side_effect = capture_start_loop

            # Create the task manager
            create_sync_periodic_task_manager(callback, 1)

            # Mock the logger and run the loop with a short timeout
            with (
                patch("obp_accounting_sdk.utils.L.debug") as mock_debug,
                patch("threading.Event") as mock_event_class,
            ):
                # Create a mock event that will timeout quickly
                mock_event = Mock()
                mock_event.is_set.side_effect = [False, False, True]  # Allow 2 loops then stop
                mock_event.wait.side_effect = [False, False]  # Don't timeout, let callback run
                mock_event_class.return_value = mock_event

                # Run the loop
                start_loop_func()

                # Should have called the callback twice
                assert call_count == 2

                # Should have logged graceful exit
                mock_debug.assert_called_with("Task loop exiting gracefully")

    @staticmethod
    def test_sync_periodic_task_manager_internal_loop_shutdown_event():
        """Test shutdown event handling in the internal loop."""
        call_count = 0

        def callback():
            nonlocal call_count
            call_count += 1

        # Mock the multiprocessing part to run the loop directly
        with patch("obp_accounting_sdk.utils.create_cancellable_sync_task") as mock_create_task:
            # Capture the start_loop function
            start_loop_func = None

            def capture_start_loop(func):
                nonlocal start_loop_func
                start_loop_func = func
                return lambda: None  # Return a dummy cancel function

            mock_create_task.side_effect = capture_start_loop

            # Create the task manager
            create_sync_periodic_task_manager(callback, 1)

            # Mock the logger and run the loop with shutdown event timeout
            with (
                patch("obp_accounting_sdk.utils.L.debug") as mock_debug,
                patch("threading.Event") as mock_event_class,
            ):
                # Create a mock event that will timeout on wait
                mock_event = Mock()
                mock_event.is_set.side_effect = [False, True]  # One loop then stop
                mock_event.wait.return_value = True  # Simulate timeout/shutdown
                mock_event_class.return_value = mock_event

                # Run the loop
                start_loop_func()

                # Should not have called the callback due to shutdown
                assert call_count == 0

                # Should have logged graceful exit
                mock_debug.assert_called_with("Task loop exiting gracefully")
