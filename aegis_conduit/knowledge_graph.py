"""Lightweight humanitarian knowledge graph using networkx."""
from __future__ import annotations

from typing import Dict, Any, Optional, List
try:
    import networkx as nx
except Exception:
    nx = None


class KnowledgeGraph:
    def __init__(self):
        if nx is None:
            self._graph = None
        else:
            self._graph = nx.Graph()

    def add_node(self, node_id: str, **attrs: Any) -> None:
        if self._graph is None:
            return
        self._graph.add_node(node_id, **attrs)

    def add_edge(self, a: str, b: str, **attrs: Any) -> None:
        if self._graph is None:
            return
        self._graph.add_edge(a, b, **attrs)

    def add_report(self, report: Dict[str, Any]) -> None:
        if self._graph is None:
            return
        # derive simple nodes
        rtype = report.get("type") or "report"
        rid = report.get("id") or f"report-{len(self._graph)}"
        attrs = dict(report)
        attrs["type"] = rtype
        self.add_node(rid, **attrs)
        # link to source
        source = report.get("source")
        if source:
            self.add_node(source, type="actor")
            self.add_edge(rid, source, relation="reported_by")

    def query_related(self, node_id: str, depth: int = 1) -> Optional[List[str]]:
        if self._graph is None:
            return None
        if node_id not in self._graph:
            return []
        return list(nx.single_source_shortest_path(self._graph, node_id, cutoff=depth).keys())
