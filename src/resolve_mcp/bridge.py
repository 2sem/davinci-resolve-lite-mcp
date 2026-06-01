"""Serialize all Resolve API access onto the main script thread.

Resolve scripting objects are not assumed thread-safe. HTTP handler threads
enqueue ``func(resolve)`` jobs; the main thread runs them one at a time.
"""

import threading
from queue import Queue


class ResolveBridge:
    """Serializes Resolve API access onto the main script thread."""

    _STOP = object()

    def __init__(self, resolve):
        self.resolve = resolve
        self._queue = Queue()

    def call(self, func):
        """Run ``func(resolve)`` on the main thread, return its result.

        Blocks the calling (HTTP handler) thread until done. Exceptions raised
        by ``func`` are re-raised here.
        """
        done = threading.Event()
        box = {}

        def job():
            try:
                box["result"] = func(self.resolve)
            except Exception as exc:  # noqa: BLE001
                box["error"] = exc
            finally:
                done.set()

        self._queue.put(job)
        done.wait()
        if "error" in box:
            raise box["error"]
        return box.get("result")

    def stop(self):
        self._queue.put(self._STOP)

    def run_forever(self):
        """Main-thread loop. Returns when stop() is called."""
        while True:
            job = self._queue.get()
            if job is self._STOP:
                return
            job()
