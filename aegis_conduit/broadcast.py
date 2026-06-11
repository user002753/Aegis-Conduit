"""Simple in-memory broadcaster for route updates (SSE pub/sub).

Each subscriber receives route snapshots via an asyncio.Queue. The
broadcaster exposes `subscribe()` to get a queue and `publish()` to push
the latest routes to all subscribers.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List


class RouteBroadcaster:
    def __init__(self) -> None:
        self._subs: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subs.remove(q)
        except ValueError:
            pass

    async def publish(self, payload: Dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                # Use nowait so a slow subscriber cannot block broadcasts.
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # If a subscriber is slow, drop the update for that subscriber
                continue
