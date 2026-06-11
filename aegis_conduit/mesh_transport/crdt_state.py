"""CRDT state scaffold for offline-first conflict-free merging.

This provides a minimal grow-only set and a placeholder for richer CRDTs.
Replace or extend with a library like `automerge` or a custom operation-based CRDT.
"""
from __future__ import annotations

from typing import Any, Dict, Set
import threading


class CRDTState:
    def __init__(self):
        self._gset: Set[str] = set()
        self._meta: Dict[str, Any] = {}
        self.lock = threading.Lock()

    def add(self, key: str) -> None:
        with self.lock:
            self._gset.add(key)

    def merge(self, other: "CRDTState") -> None:
        with self.lock:
            self._gset.update(other._gset)
            self._meta.update(other._meta)

    def dump(self) -> Dict[str, Any]:
        with self.lock:
            return {"gset": list(self._gset), "meta": dict(self._meta)}
