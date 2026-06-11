"""Bluetooth transport adapter stub.

In a full implementation this would use platform-specific Bluetooth APIs
(pybluez, bleak) or a native helper to discover peers and exchange payloads.
"""
from __future__ import annotations

from typing import Callable, Dict, Any


class BluetoothAdapter:
    def __init__(self):
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def send(self, payload: Dict[str, Any]) -> None:
        # TODO: implement BLE or classic L2CAP/TCP bridging
        pass
