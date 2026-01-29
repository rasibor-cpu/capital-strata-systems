from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any, Dict, Optional, Tuple


# -----------------------------
# Config
# -----------------------------
@dataclass
class FXRuleConfig:
    """
    FX-specific risk/regime gates that run BEFORE RegimeGate/VWAP.
    Prompt-only safe defaults.

    Times are evaluated in UTC unless stated otherwise.
    """
    enable_session_filter: bool = True
    enable_rollover_block: bool = True
    enable_news_block: bool = True

    # Session windows (UTC). Simple and conservative.
    # London ~ 07:00–16:00 UTC, NY ~ 12:00–21:00 UTC, overlap ~ 12:00–16:00 UTC
    allow_sessions: Tuple[str, ...] = ("LONDON", "NY", "OVERLAP")

    # Rollover / liquidity hole window around 5pm New York.
    # 5pm NY is 22:00 UTC during standard time; 21:00 UTC during daylight time.
    # We use a conservative UTC block that catches both: 21:00–23:00 UTC.
    rollover_block_start_utc: time = time(21, 0)
    rollover_block_end_utc: time = time(23, 0)

    # News window blocks (manual list, UTC). Later replaced by Reuters/Refinitiv.
    # Format: list of (start_utc, end_utc, label)
    news_blocks: Tuple[Tuple[time, time, str], ...] = (
        # Example: major releases window (placeholder)
        (time(12, 25), time(13, 10), "US_Macro_Window"),
    )


# -----------------------------
# Helpers
# -----------------------------
def _to_dt_utc(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        # ensure tz-aware UTC if possible
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    # try parsing ISO-ish
    try:
        s = str(ts).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _in_time_window(t: time, start: time, end: time) -> bool:
    """
    Handles windows that may wrap midnight.
    """
    if start <= end:
        return start <= t <= end
    return (t >= start) or (t <= end)


def classify_session_utc(dt_utc: datetime) -> str:
    """
    Simple FX session classification by UTC hour.
    """
    h = dt_utc.hour
    # Rough session bands (UTC):
    # Asia: 00–06
    # London: 07–11
    # Overlap: 12–15
    # NY: 16–21
    # Late: 22–23
    if 0 <= h <= 6:
        return "ASIA"
    if 7 <= h <= 11:
        return "LONDON"
    if 12 <= h <= 15:
        return "OVERLAP"
    if 16 <= h <= 21:
        return "NY"
    return "LATE"


# -----------------------------
# Main rule gate
# -----------------------------
def fx_rules_allow(*, ts_utc: Any, cfg: FXRuleConfig) -> Dict[str, Any]:
    """
    Returns dict with:
      allow: bool
      reason: str
      session: str
    """
    dt = _to_dt_utc(ts_utc)
    if dt is None:
        # fail-safe: allow (we don't want to block on parse errors in prompt-only stage)
        return {"allow": True, "reason": "ts_parse_failed_allow", "session": "UNKNOWN"}

    session = classify_session_utc(dt)

    # 1) Session filter
    if cfg.enable_session_filter:
        if session not in cfg.allow_sessions:
            return {"allow": False, "reason": f"session_block:{session}", "session": session}

    # 2) Rollover block
    if cfg.enable_rollover_block:
        t = dt.time()
        if _in_time_window(t, cfg.rollover_block_start_utc, cfg.rollover_block_end_utc):
            return {"allow": False, "reason": "rollover_block", "session": session}

    # 3) Manual news blocks (placeholder until Reuters)
    if cfg.enable_news_block:
        t = dt.time()
        for start, end, label in cfg.news_blocks:
            if _in_time_window(t, start, end):
                return {"allow": False, "reason": f"news_block:{label}", "session": session}

    return {"allow": True, "reason": "fx_rules_allow", "session": session}