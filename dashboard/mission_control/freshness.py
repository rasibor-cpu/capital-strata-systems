from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


FRESH = "FRESH"
AGING = "AGING"
STALE = "STALE"
UNAVAILABLE = "UNAVAILABLE"
UNKNOWN = "UNKNOWN"

MANDATORY_SECTIONS = ("platform", "runtime_snapshot", "runtime", "brokers", "certification", "safety")


def build_freshness_summary(
    source_registry: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime | None = None,
    fresh_seconds: int = 60,
    stale_seconds: int = 300,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    sections: dict[str, dict[str, Any]] = {}
    stale_mandatory: list[str] = []

    for section, descriptor in source_registry.items():
        observed_at = str(descriptor.get("observed_at") or descriptor.get("generated_at") or "UNAVAILABLE")
        age = _age_seconds(observed_at, current)
        status = _freshness_status(descriptor, age, fresh_seconds=fresh_seconds, stale_seconds=stale_seconds)
        if section in MANDATORY_SECTIONS and status in {STALE, UNAVAILABLE, UNKNOWN}:
            stale_mandatory.append(section)
        sections[section] = {
            "source": descriptor.get("source", "UNKNOWN"),
            "generated_at": descriptor.get("generated_at", "UNAVAILABLE"),
            "observed_at": observed_at,
            "age_seconds": age,
            "freshness_status": status,
            "stale_reason": _stale_reason(descriptor, status, age, stale_seconds),
        }

    overall = FRESH
    statuses = {entry["freshness_status"] for entry in sections.values()}
    if stale_mandatory:
        overall = STALE
    elif UNAVAILABLE in statuses:
        overall = UNAVAILABLE
    elif STALE in statuses:
        overall = STALE
    elif AGING in statuses:
        overall = AGING
    elif UNKNOWN in statuses:
        overall = UNKNOWN

    return {
        "overall_freshness": overall,
        "generated_at": current.isoformat(),
        "stale_mandatory_data": bool(stale_mandatory),
        "stale_mandatory_sections": stale_mandatory,
        "sections": sections,
    }


def _age_seconds(timestamp: str, now: datetime) -> float | str:
    if timestamp in {"", "UNAVAILABLE", "DATA UNAVAILABLE", "UNKNOWN"}:
        return "UNAVAILABLE"
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return "UNAVAILABLE"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return round(max((now - parsed.astimezone(timezone.utc)).total_seconds(), 0.0), 3)


def _freshness_status(
    descriptor: Mapping[str, Any],
    age_seconds: float | str,
    *,
    fresh_seconds: int,
    stale_seconds: int,
) -> str:
    if descriptor.get("source") == "UNAVAILABLE":
        return UNAVAILABLE
    if age_seconds == "UNAVAILABLE":
        return UNKNOWN
    if float(age_seconds) <= fresh_seconds:
        return FRESH
    if float(age_seconds) <= stale_seconds:
        return AGING
    return STALE


def _stale_reason(
    descriptor: Mapping[str, Any],
    status: str,
    age_seconds: float | str,
    stale_seconds: int,
) -> str:
    if status == UNAVAILABLE:
        return str(descriptor.get("unavailable_reason") or "source_unavailable")
    if status == UNKNOWN:
        return "timestamp_unavailable"
    if status == STALE:
        return f"age_seconds_exceeds_{stale_seconds}:{age_seconds}"
    return ""


__all__ = [
    "AGING",
    "FRESH",
    "MANDATORY_SECTIONS",
    "STALE",
    "UNAVAILABLE",
    "UNKNOWN",
    "build_freshness_summary",
]
