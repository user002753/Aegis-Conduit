"""Wi-Fi Direct transport adapter stub.

Placeholder for platform-specific Wi-Fi Direct peer discovery and data exchange.
"""
from __future__ import annotations

from typing import Dict, Any


class WifiDirectAdapter:
    def __init__(self):
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def send(self, payload: Dict[str, Any]) -> None:
        # TODO: implement Wi-Fi Direct send
        pass
