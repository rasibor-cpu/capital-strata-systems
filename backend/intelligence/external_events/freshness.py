"""Freshness / staleness evaluation for MI-EXT-001."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from backend.intelligence.external_events.constants import DEFAULT_FRESHNESS_WINDOWS_SEC, UNKNOWN


def _parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text or text in {UNKNOWN, "UNAVAILABLE"}:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def freshness_family_for_category(category: str) -> str:
    mapping = {
        "monetary_policy": "central_bank_decision",
        "interest_rates": "central_bank_decision",
        "inflation": "macroeconomic_release",
        "employment": "macroeconomic_release",
        "gdp_growth": "macroeconomic_release",
        "regulatory_action": "regulatory_announcement",
        "crypto_regulation": "regulatory_announcement",
        "issuer_earnings": "issuer_filing",
        "dividends": "issuer_filing",
        "corporate_actions": "issuer_filing",
        "mergers_acquisitions": "issuer_filing",
        "capital_raising": "issuer_filing",
        "market_disruption": "real_time_market_alert",
        "exchange_outage": "real_time_market_alert",
        "broker_outage": "real_time_market_alert",
        "volatility_event": "real_time_market_alert",
    }
    return mapping.get(str(category or "").strip(), "default")


def evaluate_freshness(
    *,
    published_at: str,
    retrieved_at: str | None = None,
    now_utc: datetime | None = None,
    category: str = "unknown",
    source_row: Mapping[str, Any] | None = None,
) -> str:
    now = now_utc or datetime.now(timezone.utc)
    published = _parse_utc(published_at)
    if published is None:
        retrieved = _parse_utc(retrieved_at or "")
        if retrieved is None:
            return UNKNOWN
        published = retrieved

    age = max(0.0, (now - published).total_seconds())
    family = freshness_family_for_category(category)
    windows = dict(DEFAULT_FRESHNESS_WINDOWS_SEC.get(family, DEFAULT_FRESHNESS_WINDOWS_SEC["default"]))
    if source_row and isinstance(source_row.get("freshness_windows_sec"), Mapping):
        windows.update({k: float(v) for k, v in source_row["freshness_windows_sec"].items()})

    if age <= float(windows["fresh"]):
        return "FRESH"
    if age <= float(windows["aging"]):
        return "AGING"
    if age <= float(windows["stale"]):
        return "STALE"
    if age <= float(windows["expired"]):
        return "EXPIRED"
    return "EXPIRED"


def is_actionable_freshness(status: str) -> bool:
    return str(status).upper() in {"FRESH", "AGING"}
