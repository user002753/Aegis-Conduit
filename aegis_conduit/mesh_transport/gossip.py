"""Gossip protocol scaffold for efficient propagation of state and updates.

This module provides a small API for publishing and subscribing to topics
and for merging received deltas into a CRDT state. It is intentionally
transport-agnostic: transport adapters (bluetooth/wifi/lora) should call
`receive()` with incoming payloads.
"""
from __future__ import annotations

from typing import Any, Dict, Callable
import threading


class GossipProtocol:
    def __init__(self):
        self.subscribers: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self.lock = threading.Lock()

    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Publish a payload to local subscribers (and to outbound transports)."""
        with self.lock:
            for cb in list(self.subscribers.values()):
                try:
                    cb(payload)
                except Exception:
                    pass

    def subscribe(self, name: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self.lock:
            self.subscribers[name] = callback

    def unsubscribe(self, name: str) -> None:
        with self.lock:
            self.subscribers.pop(name, None)

    def receive(self, raw_payload: Dict[str, Any]) -> None:
        """Called by transports when a message is received; merges into local state via subscribers."""
        # For now, just publish to subscribers. Merging into CRDT happens elsewhere.
        self.publish("inbound", raw_payload)
