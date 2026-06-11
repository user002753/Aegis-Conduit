"""Mesh transport scaffolds: gossip, CRDT state, and transport adapters.

These are lightweight stubs intended as a starting point for implementing
CRDT-based offline-first replication, gossip dissemination, and multiple
opportunistic transports (Bluetooth, Wi-Fi Direct, LoRa).
"""

from .gossip import GossipProtocol
from .crdt_state import CRDTState

__all__ = ["GossipProtocol", "CRDTState"]
