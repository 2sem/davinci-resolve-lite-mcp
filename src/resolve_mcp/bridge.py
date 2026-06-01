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
        self._stopped = False

    def call(self, func):
        """Run ``func(resolve)`` on the main thread, return its result.

        Blocks the calling (HTTP handler) thread until done. Exceptions raised
        by ``func`` are re-raised here.
        """
        if self._stopped:
            # Server is shutting down: don't enqueue work that will never run
            # (the main loop has stopped) — fail fast instead of blocking forever.
            raise RuntimeError("Server is stopping.")
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
        self._stopped = True
        self._queue.put(self._STOP)

    def run_forever(self):
        """Main-thread loop. Returns when stop() is called.

        On stop, drain any jobs already queued ahead of (or behind) the STOP
        sentinel so their callers unblock instead of hanging on done.wait().
        """
        while True:
            job = self._queue.get()
            if job is self._STOP:
                while not self._queue.empty():
                    pending = self._queue.get_nowait()
                    if pending is not self._STOP:
                        pending()
                return
            job()
