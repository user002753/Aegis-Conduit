"""Simple weather/sensor feed simulator for hazard events.

This adapter emits hazard events (batched) that the `RouteEvaluator` can
ingest via `ingest_hazard`. The implementation is lightweight and intended
for local simulation or wiring to real sensor streams later.
"""

from __future__ import annotations

from typing import Any, Iterable


class WeatherFeedSimulator:
    def __init__(self, emit_sequence: Iterable[dict[str, Any]] | None = None) -> None:
        # emit_sequence is an iterable of hazard event dicts
        self.emit_sequence = list(emit_sequence) if emit_sequence is not None else []

    def add_event(self, event: dict[str, Any]) -> None:
        self.emit_sequence.append(event)

    def stream(self):
        """Yield hazard events one by one."""
        for evt in self.emit_sequence:
            yield evt
