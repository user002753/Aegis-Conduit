"""Communications suite: broadcast alerts, priority channels, compression helpers."""
from __future__ import annotations

from typing import Dict, Any
import json
import zlib


class BroadcastManager:
    def __init__(self):
        self.channels = {"default": []}

    def broadcast(self, channel: str, msg: Dict[str, Any]) -> None:
        # In a real implementation this would push to SMS, radio, or mesh transports
        self.channels.setdefault(channel, []).append(msg)

    def get_channel(self, channel: str):
        return list(self.channels.get(channel, []))


def compress_message(msg: Dict[str, Any]) -> bytes:
    raw = json.dumps(msg).encode("utf-8")
    return zlib.compress(raw)

def decompress_message(payload: bytes) -> Dict[str, Any]:
    raw = zlib.decompress(payload)
    return json.loads(raw.decode("utf-8"))
