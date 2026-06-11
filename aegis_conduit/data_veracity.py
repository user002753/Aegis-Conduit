"""Data verification and trust scoring for incident reports.

This module integrates cryptographic verification (ed25519), a TrustEngine
for multi-factor scoring, and FoundryIQ cross-references to produce a
composite confidence score for incoming reports.
"""

from datetime import datetime
from typing import Any, List

from .foundry_iq import FoundryIQ
from .trust import TrustEngine
from .identity import IdentityManager


class VeracityEngine:
    def __init__(self) -> None:
        self.trusted_sources: set[str] = {
            "district_authority",
            "emergency_authority",
            "red_cross",
            "verified_ngo",
            "local_command_center",
        }
        self.foundry = FoundryIQ()
        self.trust_engine = TrustEngine()
        self.identity = IdentityManager()

    def validate_report(self, report: dict[str, Any], corroborating: List[dict] | None = None) -> dict[str, Any]:
        """Cross-reference incoming data against trusted sources and protocols.

        Returns a dict containing `trusted`, `confidence`, and the normalized event.
        """
        corroborating = corroborating or []
        source = report.get("source", "unknown")
        event = report.get("event", {})

        # Foundry registry cross-reference
        registry_result = self.foundry.cross_reference(event)
        registry_trusted = bool(registry_result.get("trusted")) if isinstance(registry_result, dict) else bool(registry_result)
        registry_score = 0.25 if registry_trusted else 0.0

        # cryptographic verification
        crypto_valid = False
        try:
            if report.get("signature"):
                crypto_valid = bool(self.identity.verify_report(report))
        except Exception:
            crypto_valid = False
        crypto_score = 1.0 if crypto_valid else 0.0

        # reputation + corroboration via TrustEngine
        trust_score = self.trust_engine.trust_score(report, corroborating)

        # source / authority contribution (backwards-compatible)
        source_score = 1.0 if source in self.trusted_sources else 0.25
        authority_score = 1.0 if event.get("verified_by") in self.trusted_sources else 0.0

        # Composite confidence: a report can pass through either strong
        # cryptographic proof or a trusted-source plus registry evidence path.
        confidence = min(
            1.0,
            (0.30 * crypto_score)
            + (0.10 * trust_score)
            + (0.25 * source_score)
            + (0.20 * authority_score)
            + registry_score,
        )

        trusted = confidence >= 0.7

        flags: list[str] = []
        if not trusted:
            flags.append("untrusted_source")
        if event.get("type") == "claim" and not registry_score:
            flags.append("needs_cross_reference")
        if not crypto_valid:
            flags.append("signature_missing_or_invalid")

        return {
            "trusted": trusted,
            "source": source,
            "event": event,
            "type": report.get("type", "unknown"),
            "confidence": float(confidence),
            "validated_at": datetime.utcnow().isoformat() + "Z",
            "flags": flags,
            "crypto_valid": bool(crypto_valid),
        }
