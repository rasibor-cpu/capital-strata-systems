"""Phase 178A — freshness limits for Options Income advisory inputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Soft limits (seconds). Exceeding → STALE (not silently treated as live).
FRESHNESS_LIMITS_SECONDS: dict[str, int] = {
    "underlying_quote": 120,
    "option_chain_quote": 300,
    "holdings": 900,
    "balances": 900,
    "greeks": 300,
    "volatility_history": 86400,
    "market_calendar": 86400,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def age_seconds(provider_timestamp: str | None, *, now: str | None = None) -> float | None:
    if not provider_timestamp:
        return None
    try:
        first = datetime.fromisoformat(str(provider_timestamp).replace("Z", "+00:00"))
        second = datetime.fromisoformat(str(now or utc_now()).replace("Z", "+00:00"))
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        if second.tzinfo is None:
            second = second.replace(tzinfo=timezone.utc)
        return max(0.0, (second - first).total_seconds())
    except Exception:
        return None


def evaluate_freshness(
    data_type: str,
    *,
    provider_timestamp: str | None,
    now: str | None = None,
) -> dict[str, Any]:
    limit = int(FRESHNESS_LIMITS_SECONDS.get(data_type, 900))
    age = age_seconds(provider_timestamp, now=now)
    generated = now or utc_now()
    if provider_timestamp is None:
        return {
            "data_type": data_type,
            "limit_seconds": limit,
            "age_seconds": None,
            "freshness": "UNKNOWN",
            "stale": True,
            "stale_reason": "missing_provider_timestamp",
            "generated_at": generated,
            "provider_timestamp": None,
        }
    if age is None:
        return {
            "data_type": data_type,
            "limit_seconds": limit,
            "age_seconds": None,
            "freshness": "UNKNOWN",
            "stale": True,
            "stale_reason": "unparseable_timestamp",
            "generated_at": generated,
            "provider_timestamp": provider_timestamp,
        }
    stale = age > limit
    return {
        "data_type": data_type,
        "limit_seconds": limit,
        "age_seconds": round(age, 3),
        "freshness": "STALE" if stale else "FRESH",
        "stale": stale,
        "stale_reason": f"age_exceeds_{limit}s" if stale else None,
        "generated_at": generated,
        "provider_timestamp": provider_timestamp,
    }


__all__ = ["FRESHNESS_LIMITS_SECONDS", "age_seconds", "evaluate_freshness", "utc_now"]
