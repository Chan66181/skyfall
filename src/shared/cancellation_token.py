import threading
import time
from typing import Callable, Optional

class OperationCanceledError(Exception):
    """Exception raised when an operation is cancelled."""
    def __init__(self, message="The operation was canceled."):
        self.message = message
        super().__init__(self.message)

class CancellationToken:
    """
    A token to signal cancellation of an operation.

    This class allows for cooperative cancellation of asynchronous operations.
    It can be configured with a timeout to automatically cancel after a
    specified duration. It also supports a callback function that runs in a
    separate thread and can be used to monitor for cancellation signals
    from external sources.
    """
    def __init__(self, timeout: Optional[float] = None, callback: Optional[Callable[[], bool]] = None):
        """
        Initializes the CancellationToken.

        Args:
            timeout: The time in seconds after which the token is automatically cancelled.
            callback: A function that will be called periodically. If it returns True,
                      the token is cancelled.
        """
        self._is_cancelled = False
        self._lock = threading.Lock()
        self._callback = callback
        self._timer: Optional[threading.Timer] = None
        self._callback_thread: Optional[threading.Thread] = None

        if timeout is not None:
            self._timer = threading.Timer(timeout, self.cancel)
            self._timer.start()

        if self._callback:
            self._callback_thread = threading.Thread(target=self._run_callback, daemon=True)
            self._callback_thread.start()

    def _run_callback(self):
        """
        Runs the callback function in a loop until the token is cancelled
        or the callback signals cancellation.
        """
        while not self.is_cancelled():
            if self._callback and self._callback():
                self.cancel()
                break
            time.sleep(0.1) # Prevents busy-waiting

    def cancel(self):
        """
        Manually signals cancellation.

        This is thread-safe. Once a token is cancelled, it cannot be un-cancelled.
        """
        with self._lock:
            if not self._is_cancelled:
                self._is_cancelled = True
                if self._timer:
                    self._timer.cancel() # Cancel the timer if it's running

    def is_cancelled(self) -> bool:
        """
        Checks if cancellation has been requested for this token.

        Returns:
            True if cancellation has been requested, False otherwise.
        """
        with self._lock:
            return self._is_cancelled

    def throwIfCancellationRequested(self):
        """
        Raises an OperationCanceledError if cancellation has been requested.

        This provides a convenient way for an operation to check for cancellation
        and exit if needed.
        """
        if self.is_cancelled():
            raise OperationCanceledError()

