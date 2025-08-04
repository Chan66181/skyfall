import threading

class CancellationToken:
    def __init__(self):
        self._event = threading.Event()

    def cancel(self):
        self._event.set()

    def is_cancelled(self):
        return self._event.is_set()

    def wait(self, timeout=None):
        return self._event.wait(timeout)
