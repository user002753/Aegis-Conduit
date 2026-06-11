"""Foundry IQ connector with safe, opt-in external integration.

This module exposes `FoundryIQ` which will use a local in-memory stub by
default. If both `FOUNDRY_API_URL` and `FOUNDRY_API_KEY` are set in the
environment the connector will attempt to call the configured Foundry
endpoint for knowledge-grounding queries. Network calls are optional and
opt-in; no credentials are stored in the repo.
"""

from typing import Any, Dict
import os
import json
import re

try:
    import requests
except Exception:
    requests = None


class FoundryIQ:
    def __init__(self) -> None:
        # Local in-memory registry mapping reference_id -> expected status
        self.registry: dict[str, str] = {
            "warehouse_inventories": "verified",
            "evacuation_protocols": "active",
            "road_status_feed": "authenticated",
        }
        self.api_url = os.environ.get("FOUNDRY_API_URL")
        self.api_key = os.environ.get("FOUNDRY_API_KEY")

    def is_connected(self) -> bool:
        # Require explicit enablement to avoid accidental outbound calls.
        enabled = os.environ.get("ENABLE_FOUNDRY", "").lower() == "true"
        return bool(enabled and self.api_url and self.api_key and requests is not None)

    def cross_reference(self, event: dict[str, Any]) -> Dict[str, Any]:
        """Cross-reference an event and return a structured result.

        Returns a dict with keys: `trusted` (bool), `reason` (str), and
        `citations` (list) for evidence. If external Foundry is configured
        the connector will attempt a POST to the service and return the
        service response. Otherwise it uses the local registry stub and
        returns a simulated citation.
        """
        if not event:
            return {"trusted": False, "reason": "no event", "citations": []}

        # Opt-in external call
        # Prepare sanitized payload and allowlist check before any external call
        sanitized = self.sanitize_event(event)
        allowlist_raw = os.environ.get("FOUNDRY_ALLOWLIST", "")
        if allowlist_raw:
            allowlist = [s.strip() for s in allowlist_raw.split(",") if s.strip()]
            ref = sanitized.get("reference_id")
            if ref not in allowlist:
                return {"trusted": False, "reason": "reference_id not allowed for external lookup", "citations": []}

        if self.is_connected():
            try:
                payload = {"event": sanitized}
                headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
                resp = requests.post(self.api_url.rstrip("/") + "/ground", headers=headers, data=json.dumps(payload), timeout=3.0)
                if resp.status_code == 200:
                    # Only trust structured responses; do not forward raw external text to UI
                    return resp.json()
                else:
                    # degrade to local stub on failure
                    pass
            except Exception:
                # Network or request error; fall back to local stub
                pass

        # Local stub behavior
        ref = event.get("reference_id")
        if not ref:
            return {"trusted": False, "reason": "no reference_id", "citations": []}

        expected = self.registry.get(ref)
        trusted = bool(expected and expected == event.get("status"))
        citations = [{"source": "local_registry", "reference_id": ref, "status": expected}]
        reason = "matched registry" if trusted else "no matching registry entry or status"
        return {"trusted": trusted, "reason": reason, "citations": citations}

    def sanitize_event(self, event: dict[str, Any]) -> dict:
        """Return a sanitized copy of `event` safe for outbound calls.

        Rules:
        - Only allow a small set of fields to be sent externally.
        - Redact emails and phone numbers in `description`.
        - Truncate free text to 200 chars.
        """
        allowed_fields = ["reference_id", "status", "type", "location", "timestamp", "description"]
        out: dict[str, Any] = {}
        for k in allowed_fields:
            if k in event:
                out[k] = event[k]

        # Sanitize description
        desc = out.get("description")
        if isinstance(desc, str):
            # redact emails
            desc = re.sub(r"[\w\.-]+@[\w\.-]+", "[REDACTED_EMAIL]", desc)
            # redact phone numbers (simple heuristic)
            desc = re.sub(r"\+?\d[\d \-()]{6,}\d", "[REDACTED_PHONE]", desc)
            # truncate
            if len(desc) > 200:
                desc = desc[:197] + "..."
            out["description"] = desc

        # Ensure location is a simple [lat, lon] pair of numbers
        loc = out.get("location")
        if isinstance(loc, (list, tuple)) and len(loc) >= 2:
            try:
                lat = float(loc[0])
                lon = float(loc[1])
                out["location"] = [lat, lon]
            except Exception:
                out.pop("location", None)

        return out

    def register(self, reference_id: str, status: str) -> None:
        """Add or update a trusted registry entry (local only)."""
        self.registry[reference_id] = status
