from __future__ import annotations

from typing import Any, Dict, Iterable, List

import numpy as np

try:
    from sklearn.ensemble import IsolationForest
except Exception:  # pragma: no cover - sklearn may be absent in constrained env
    IsolationForest = None  # type: ignore


class AnomalyDetector:
    """Lightweight wrapper around an IsolationForest for edge anomaly scoring.

    If `sklearn` is not available, falls back to a simple z-score detector.
    """

    def __init__(self) -> None:
        self.model = IsolationForest(n_estimators=50, contamination=0.05) if IsolationForest is not None else None
        self._fallback_history: List[float] = []

    def _vectorize(self, packet: Dict[str, Any]) -> List[float]:
        # Build a small numeric feature vector from packet fields.
        # Features: reported severity, length of message, source token hash mod 1000
        severity = float(packet.get("severity", 0.0))
        msg_len = float(len(str(packet.get("message", ""))))
        src_hash = float(abs(hash(packet.get("source", ""))) % 1000)
        return [severity, msg_len, src_hash]

    def partial_fit(self, packets: Iterable[Dict[str, Any]]) -> None:
        X = [self._vectorize(p) for p in packets]
        if self.model is not None:
            try:
                self.model.fit(X)
            except Exception:
                # fallback: keep history
                self._fallback_history.extend([x[0] for x in X])
        else:
            self._fallback_history.extend([x[0] for x in X])

    def score_packet(self, packet: Dict[str, Any]) -> float:
        """Return an anomaly score between 0..1 where 1 is very anomalous."""
        x = np.array(self._vectorize(packet)).reshape(1, -1)
        if self.model is not None:
            try:
                # IsolationForest: -1 for anomaly, 1 for normal; use decision_function
                score = -float(self.model.decision_function(x).ravel()[0])
                # normalize roughly to 0..1
                return min(max(score, 0.0), 1.0)
            except Exception:
                pass

        # fallback: use z-score on severity over history
        if not self._fallback_history:
            return 0.0
        sev = float(packet.get("severity", 0.0))
        arr = np.array(self._fallback_history)
        mu = float(arr.mean())
        sigma = float(arr.std()) if arr.std() > 0 else 1.0
        z = abs(sev - mu) / sigma
        # map z to 0..1 (z>3 => 1.0)
        return min(1.0, z / 3.0)
