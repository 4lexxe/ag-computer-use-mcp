"""Hide an idle indicator without disconnecting the client's MCP server."""

import threading
import time
from functools import wraps


class IdleIndicator:
    def __init__(self, close, lock, timeout=8.0, clock=time.monotonic):
        self.close = close
        self.lock = lock
        self.timeout = timeout
        self.clock = clock
        self.last_activity = None
        self.active_calls = 0
        self.stopped = threading.Event()
        self.worker = None

    def touch(self):
        with self.lock:
            self.last_activity = self.clock()

    def disarm(self):
        with self.lock:
            self.last_activity = None

    def track(self, function):
        @wraps(function)
        def tracked(*args, **kwargs):
            with self.lock:
                self.active_calls += 1
            try:
                return function(*args, **kwargs)
            finally:
                with self.lock:
                    self.active_calls -= 1
                    if self.last_activity is not None:
                        self.last_activity = self.clock()

        return tracked

    def check(self):
        # The same lock guards tool startup and shutdown: a new call cannot race
        # with closing the indicator. Start the idle interval after a tool returns.
        with self.lock:
            if (
                self.last_activity is not None
                and not self.active_calls
                and self.clock() - self.last_activity >= self.timeout
            ):
                self.close()
                self.last_activity = None
                return True
        return False

    def _watch(self):
        while not self.stopped.wait(0.5):
            try:
                self.check()
            except OSError:
                # Transient state-file contention must not kill the watcher.
                continue

    def start(self):
        if self.worker is None:
            self.worker = threading.Thread(target=self._watch, name="idle-indicator", daemon=True)
            self.worker.start()

    def stop(self):
        self.stopped.set()
        if self.worker is not None:
            self.worker.join(timeout=2)
