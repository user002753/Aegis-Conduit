"""Simple scheduler to poll adapters periodically and invoke a handler."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable


class FeedScheduler:
    def __init__(self, poll_fn: Callable[[], list[dict[str, Any]]], handler: Callable[[dict[str, Any]], None], interval: float = 5.0) -> None:
        """Create a scheduler that calls `poll_fn` every `interval` seconds and passes events to `handler`.

        `poll_fn` must return a list of event dicts.
        """
        self.poll_fn = poll_fn
        self.handler = handler
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                events = self.poll_fn()
                for e in events:
                    try:
                        self.handler(e)
                    except Exception:
                        continue
            except Exception:
                pass
            # sleep in small increments to respond quickly to stop
            slept = 0.0
            while slept < self.interval and not self._stop.is_set():
                time.sleep(0.1)
                slept += 0.1

    def stop(self, timeout: float | None = None) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
