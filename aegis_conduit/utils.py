"""Shared utilities for Aegis Conduit."""

from typing import Any


def normalize_report(report: dict[str, Any]) -> dict[str, Any]:
    """Normalize incoming report payloads into a standard internal schema."""
    normalized = {
        "source": report.get("source", "unknown"),
        "type": report.get("type", "generic"),
        "timestamp": report.get("timestamp"),
        "event": report.get("event", {}),
    }
    for optional_field in ("body", "payload", "signature", "public_key"):
        if optional_field in report:
            normalized[optional_field] = report[optional_field]
    return normalized
