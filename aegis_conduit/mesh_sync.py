"""Mesh network sync utilities for decentralized crisis coordination."""

from typing import Any
from collections import deque
import os
import tempfile

from .state_store import StateStore
from .mesh_transport.crdt_state import CRDTState


class MeshSyncEngine:
    """A lightweight in-memory mesh sync simulation.

    Peers may be other `MeshSyncEngine` instances; this supports simple
    discovery, gossip, and state merge for local simulation and testing.
    """

    def __init__(self) -> None:
        self.peers: list["MeshSyncEngine"] = []
        self.local_store: dict[str, Any] = {"reports": [], "trusted_events": [], "routes": []}
        self.pending_reports: deque[dict[str, Any]] = deque()
        # Keep each simulated node isolated from the repository-level state DB.
        tmp = tempfile.NamedTemporaryFile(prefix="aegis_mesh_", suffix=".db", delete=False)
        self._tmp_path = tmp.name
        tmp.close()
        self._store = StateStore(path=self._tmp_path)
        self._store.init_db()
        # initialize a CRDT state for offline-first merges
        self.crdt = CRDTState()

    def close(self) -> None:
        """Release local persistence resources used by the simulated node."""
        self._store.close()
        try:
            os.unlink(self._tmp_path)
        except FileNotFoundError:
            pass
        except PermissionError:
            # Windows can keep SQLite files briefly locked during interpreter
            # shutdown; leaving a temp file is better than noisy demo teardown.
            pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def start(self) -> None:
        """Initialize the mesh node (no network sockets in this stub)."""
        # In a real deploy this would start discovery/listeners.
        # Load persisted state into local_store if present
        persisted = self._store.load_state()
        if persisted and any(persisted.values()):
            # merge persisted data into local_store
            self.merge_state(persisted)
        # ensure local_store contains a crdt dump for peers
        try:
            self.local_store["crdt"] = self.crdt.dump()
        except Exception:
            pass
        return

    def register_peer(self, peer: "MeshSyncEngine") -> None:
        """Register another mesh node (object reference) for gossip.

        Accepts a `MeshSyncEngine` instance so tests can simulate direct
        peer-to-peer state exchange.
        """
        if peer is self:
            return
        if peer not in self.peers:
            self.peers.append(peer)

    def post_local_report(self, report: dict[str, Any]) -> None:
        """Enqueue a local report and optimistically add to local store."""
        self.pending_reports.append(report)
        key = self._report_key(report)
        self.crdt.add(key)
        if key not in {self._report_key(r) for r in self.local_store.setdefault("reports", [])}:
            self.local_store["reports"].append(report)
        self.local_store["crdt"] = self.crdt.dump()

    def sync_state(self, state: dict[str, Any]) -> None:
        """Update local store with authoritative agent state snapshot."""
        # shallow merge of known keys
        for k, v in state.items():
            if isinstance(v, list):
                self.local_store.setdefault(k, [])
                # merge preserving order and uniqueness by simple key
                existing_keys = {self._item_key(r) for r in self.local_store[k]}
                for item in v:
                    item_key = self._item_key(item)
                    if item_key not in existing_keys:
                        self.local_store[k].append(item)
                        existing_keys.add(item_key)
            else:
                self.local_store[k] = v
        # persist authoritative snapshot
        try:
            # include CRDT dump for peer merges
            try:
                self.local_store["crdt"] = self.crdt.dump()
            except Exception:
                pass
            self._store.save_state(self.local_store)
        except Exception:
            # persistence failure should not crash the agent in simulation
            pass

    def receive(self) -> dict[str, Any] | None:
        """Pop a pending local report if available for processing by the agent."""
        if self.pending_reports:
            return self.pending_reports.popleft()
        return None

    def gossip(self) -> None:
        """Simulate a gossip round with registered peers, merging state."""
        for p in list(self.peers):
            try:
                # push our state to peer and pull theirs
                p.merge_state(self.local_store)
                self.merge_state(p.local_store)
            except Exception:
                # one peer failing shouldn't block others in the sim
                continue

    def merge_state(self, peer_state: dict[str, Any]) -> None:
        """Merge a peer's state into local_store with simple conflict resolution."""
        # if peer provides a CRDT dump, merge it into our CRDT state
        try:
            peer_crdt = peer_state.get("crdt")
            if peer_crdt:
                other = CRDTState()
                other._gset = set(peer_crdt.get("gset", []))
                other._meta = dict(peer_crdt.get("meta", {}))
                self.crdt.merge(other)
        except Exception:
            pass

        # merge reports by unique key, preferring later validated_at if present
        existing = {self._report_key(r): r for r in self.local_store.get("reports", [])}
        for r in peer_state.get("reports", []):
            if not isinstance(r, dict):
                continue
            k = self._report_key(r)
            if k not in existing:
                existing[k] = r
                self.crdt.add(k)
            else:
                # choose the report with later validated_at when available
                a = existing[k].get("validated_at")
                b = r.get("validated_at")
                if b and (not a or b > a):
                    existing[k] = r
                self.crdt.add(k)

        self.local_store["reports"] = list(existing.values())

        # merge trusted_events by simple containment
        trusted = {str(e): e for e in self.local_store.get("trusted_events", [])}
        for e in peer_state.get("trusted_events", []):
            trusted.setdefault(str(e), e)
        self.local_store["trusted_events"] = list(trusted.values())
        # ensure crdt dump is present in local_store for next sync
        try:
            self.local_store["crdt"] = self.crdt.dump()
        except Exception:
            pass

    def _item_key(self, item: Any) -> str:
        if isinstance(item, dict):
            if "route_id" in item:
                return f"route|{item['route_id']}"
            return self._report_key(item)
        return str(item)

    def _report_key(self, report: dict[str, Any]) -> str:
        if not isinstance(report, dict):
            return str(report)
        evt = report.get("event", {})
        if not isinstance(evt, dict):
            evt = {"value": evt}
        ref = evt.get("reference_id") or evt.get("type") or str(evt)
        return f"{report.get('source')}|{report.get('timestamp')}|{ref}"
