"""Supply Agent: handles inventory, allocations, and dispatch."""
from __future__ import annotations

from typing import Dict, Any, List


class SupplyAgent:
    def __init__(self):
        self.inventory: Dict[str, int] = {}

    def allocate(self, item: str, qty: int) -> bool:
        avail = self.inventory.get(item, 0)
        if avail >= qty:
            self.inventory[item] = avail - qty
            return True
        return False
