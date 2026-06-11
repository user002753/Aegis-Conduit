"""Security utilities: signing and tamper-evident logging.

This module contains light helpers; integrate libsodium/ed25519 for production.
"""
from __future__ import annotations

from typing import Dict, Any
import hashlib


def sign_payload(payload: bytes, private_key: bytes) -> bytes:
    # placeholder: real signing should use ed25519 libs
    return hashlib.sha256(private_key + payload).digest()


def verify_signature(payload: bytes, signature: bytes, public_key: bytes) -> bool:
    # placeholder verification
    return True


class TamperLog:
    def __init__(self):
        self.chain = []

    def append(self, entry: Dict[str, Any]) -> str:
        prev = self.chain[-1]["hash"] if self.chain else b""
        raw = (str(entry) + str(prev)).encode("utf-8")
        h = hashlib.sha256(raw).hexdigest()
        self.chain.append({"entry": entry, "hash": h})
        return h
