"""
Economic Event Calendar Adapter (Free / Scraped / Deterministic)
---------------------------------------------------------------
Purpose:
- Pull near-term scheduled macro events (CPI, NFP, FOMC, GDP)
- Convert them into structured records for IntelEnvelope conversion

Design principles:
- No credentials
- Low request volume
- Deterministic, auditable
- Failure-safe (never crashes engine)
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any


EVENT_FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

KEYWORDS = {
    "CPI": ["cpi", "inflation"],
    "NFP": ["non-farm", "nfp", "payroll"],
    "FOMC": ["fomc", "fed", "interest rate"],
    "GDP": ["gdp", "growth"],
    "PMI": ["pmi"],
}


def _utc_now():
    return datetime.now(timezone.utc)


def _importance_to_pressure(importance: str) -> float:
    if importance == "high":
        return 0.85
    if importance == "medium":
        return 0.70
    return 0.55


def fetch_economic_events(
    minutes_ahead: int = 360,
    max_items: int = 10,
) -> List[Dict[str, Any]]:
    """
    Fetch upcoming economic events within time window.
    Returns a list of normalized event dicts.
    """
    try:
        with urllib.request.urlopen(EVENT_FEED_URL, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return []

    now = _utc_now()
    horizon = now + timedelta(minutes=minutes_ahead)

    events: List[Dict[str, Any]] = []

    for ev in payload:
        try:
            ts = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
        except Exception:
            continue

        if not (now <= ts <= horizon):
            continue

        title = (ev.get("title") or "").lower()
        impact = (ev.get("impact") or "").lower()

        matched = None
        for k, words in KEYWORDS.items():
            if any(w in title for w in words):
                matched = k
                break

        if not matched:
            continue

        events.append(
            {
                "ts_utc": ts.isoformat(),
                "event_type": matched,
                "title": ev.get("title"),
                "country": ev.get("country"),
                "impact": impact or "low",
                "pressure": _importance_to_pressure(impact),
                "source": "economic_calendar",
            }
        )

        if len(events) >= max_items:
            break

    return events


# -----------------------------
# Self-test
# -----------------------------
if __name__ == "__main__":
    events = fetch_economic_events(minutes_ahead=720, max_items=5)
    print(f"ECON_EVENTS_FOUND: {len(events)}")
    for e in events:
        print(e)
