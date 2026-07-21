"""Phase 178A — market calendar / corporate-event disclosure for OI scoring.

Does not invent earnings, ex-dividend, or holiday dates.
"""

from __future__ import annotations

from typing import Any, Mapping

from backend.options.options_income_freshness import evaluate_freshness, utc_now


def resolve_market_event_context(
    *,
    underlying: str | None = None,
    calendar_provider: Mapping[str, Any] | None = None,
    event_provider: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ts = generated_at or utc_now()
    cal = dict(calendar_provider or {})
    events = dict(event_provider or {})

    if not cal and not events:
        return {
            "status": "EVENT_DATA_UNAVAILABLE",
            "underlying": underlying,
            "market_closed": None,
            "holiday": None,
            "early_close": None,
            "earnings_proximity": None,
            "ex_dividend_proximity": None,
            "corporate_action": None,
            "option_expiration_timing": None,
            "limitation": "No approved market-calendar or corporate-event source configured",
            "invented_dates": False,
            "provenance": "CONFIGURATION",
            "freshness": "UNKNOWN",
            "generated_at": ts,
            "advisory_only": True,
        }

    provider_ts = cal.get("timestamp") or events.get("timestamp")
    fresh = evaluate_freshness("market_calendar", provider_timestamp=provider_ts, now=ts)
    return {
        "status": "READY" if not fresh["stale"] else "STALE",
        "underlying": underlying,
        "market_closed": cal.get("market_closed"),
        "holiday": cal.get("holiday"),
        "early_close": cal.get("early_close"),
        "earnings_proximity": events.get("earnings_proximity"),
        "ex_dividend_proximity": events.get("ex_dividend_proximity"),
        "corporate_action": events.get("corporate_action"),
        "option_expiration_timing": events.get("option_expiration_timing"),
        "limitation": None,
        "invented_dates": False,
        "provenance": str(cal.get("provenance") or events.get("provenance") or "MARKET_DATA_PROVIDER"),
        "freshness": fresh.get("freshness"),
        "age_seconds": fresh.get("age_seconds"),
        "generated_at": ts,
        "advisory_only": True,
    }


__all__ = ["resolve_market_event_context"]
