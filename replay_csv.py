"""
CSV Replay Engine (EngineLoop-compatible, ts_utc fix)
----------------------------------------------------
Replays OHLCV bars into EngineLoop.

Fixes:
- Bar is a dataclass with attributes (bar.symbol, bar.open, ...)
- Adds bar.ts_utc as a timezone-aware datetime (EngineLoop requires it)
- Robust CSV header mapping (Open/open/Adj Close/etc.)
- Calls engine.on_bar(...) with only supported kwargs (signature-inspected)
"""

from dataclasses import dataclass
from typing import Dict, Any, Iterator, Optional, List
import csv
from datetime import datetime, timezone
import inspect


# -------------------------
# Config
# -------------------------
@dataclass
class CSVReplayConfig:
    csv_path: str
    symbol: str = "SPY"


# -------------------------
# Bar object (EngineLoop expects attributes)
# -------------------------
@dataclass
class Bar:
    symbol: str
    ts_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    timestamp_raw: Optional[str] = None  # optional: keep original string


# -------------------------
# Helpers
# -------------------------
def _norm_key(k: str) -> str:
    return (k or "").strip().lower()

def _to_float(x: Any) -> float:
    if x is None:
        return 0.0
    s = str(x).strip()
    if s == "":
        return 0.0
    s = s.replace(",", "")
    return float(s)

def _pick(row_norm: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for k in keys:
        if k in row_norm and row_norm[k] not in (None, ""):
            return row_norm[k]
    return None

def _available_headers(fieldnames: Optional[List[str]]) -> List[str]:
    return [h for h in (fieldnames or []) if h is not None]

def _parse_ts_utc(ts: Optional[Any]) -> datetime:
    """
    Parse timestamp into timezone-aware UTC datetime.
    Supports:
      - Unix epoch seconds / milliseconds
      - ISO 8601 strings (with or without Z)
    Falls back to now(UTC) if unknown.
    """
    if ts is None:
        return datetime.now(timezone.utc)

    s = str(ts).strip()
    if s == "":
        return datetime.now(timezone.utc)

    # Numeric epoch?
    try:
        num = float(s)
        # if looks like milliseconds
        if num > 10_000_000_000:  # ~ year 2286 in seconds; so likely ms
            num = num / 1000.0
        return datetime.fromtimestamp(num, tz=timezone.utc)
    except Exception:
        pass

    # ISO-like strings
    try:
        # Handle trailing Z
        if s.endswith("Z"):
            s2 = s[:-1] + "+00:00"
        else:
            s2 = s

        dt = datetime.fromisoformat(s2)
        # If naive, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


# -------------------------
# CSV iterator
# -------------------------
def iter_csv_bars(cfg: CSVReplayConfig) -> Iterator[Bar]:
    """
    Yield Bar objects from CSV.

    Required: open/high/low/close (case-insensitive, supports variants)
    Optional: volume
    Optional: timestamp/time/datetime/date
    """
    with open(cfg.csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = _available_headers(reader.fieldnames)

        ts_keys = ["timestamp", "time", "datetime", "date", "dt"]
        open_keys = ["open", "o", "open_price"]
        high_keys = ["high", "h", "high_price"]
        low_keys  = ["low", "l", "low_price"]
        close_keys = [
            "close", "c", "close_price",
            "adj close", "adj_close",
            "adjusted close", "adjusted_close"
        ]
        vol_keys = ["volume", "vol", "v"]

        for row in reader:
            row_norm = {_norm_key(k): v for k, v in (row or {}).items()}

            ts_raw = _pick(row_norm, ts_keys)
            o = _pick(row_norm, open_keys)
            h = _pick(row_norm, high_keys)
            l = _pick(row_norm, low_keys)
            c = _pick(row_norm, close_keys)
            v = _pick(row_norm, vol_keys)

            if o is None or h is None or l is None or c is None:
                raise KeyError(
                    "CSV is missing one or more OHLC columns. "
                    f"Found headers: {headers}. "
                    "Expected variants like Open/High/Low/Close (case-insensitive) "
                    "or Adj Close for close."
                )

            yield Bar(
                symbol=cfg.symbol,
                ts_utc=_parse_ts_utc(ts_raw),
                open=_to_float(o),
                high=_to_float(h),
                low=_to_float(l),
                close=_to_float(c),
                volume=_to_float(v) if v is not None else 0.0,
                timestamp_raw=str(ts_raw) if ts_raw is not None else None,
            )


# -------------------------
# Replay
# -------------------------
def replay(cfg: CSVReplayConfig, engine) -> Dict[str, Any]:
    """
    Replay CSV bars through EngineLoop.

    Calls engine.on_bar(bar, ...) using only supported kwargs.
    """
    bars_1m = 0
    prompts = 0

    on_bar_sig = inspect.signature(engine.on_bar)
    accepted = set(on_bar_sig.parameters.keys())

    for bar in iter_csv_bars(cfg):
        received_at = datetime.now(timezone.utc)

        kwargs = {}
        if "received_at_utc" in accepted:
            kwargs["received_at_utc"] = received_at
        elif "received_at" in accepted:
            kwargs["received_at"] = received_at
        elif "ts" in accepted:
            kwargs["ts"] = received_at

        snap = engine.on_bar(bar, **kwargs)

        bars_1m += 1

        if isinstance(snap, dict):
            if snap.get("prompt") or snap.get("prompt_text") or snap.get("prompt_payload"):
                prompts += 1

    return {
        "bars_1m": bars_1m,
        "prompts_queued": prompts,
    }