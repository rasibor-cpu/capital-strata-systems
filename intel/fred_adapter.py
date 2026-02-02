"""
REA Capital – FRED Macro Series Adapter (FREE, HARDENED)
-------------------------------------------------------
Purpose:
- Pull macroeconomic time series from FRED
- Normalize into MacroSeriesPoint objects
- Fail gracefully on HTTP errors (incl 400)
- Optional audit logging to audit_logs/

Requires (recommended):
- FRED_API_KEY environment variable (free key)
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MacroSeriesPoint:
    ts_utc: str
    provider: str
    series_id: str
    date: str
    value: Optional[float]
    realtime_start: Optional[str]
    realtime_end: Optional[str]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask(s: Optional[str]) -> str:
    if not s:
        return "MISSING"
    if len(s) <= 6:
        return "***"
    return s[:3] + "***" + s[-3:]


def http_get_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "REA-Capital/1.0 (fred adapter)",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return {}

    if not raw:
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def build_fred_url(series_id: str, api_key: Optional[str], limit: int) -> str:
    # FRED is picky; always include these params
    params = {
        "series_id": series_id,
        "file_type": "json",
        "sort_order": "desc",
        "limit": str(limit),
    }
    # Many environments work better if api_key is always present
    if api_key:
        params["api_key"] = api_key

    return f"{FRED_BASE}?{urllib.parse.urlencode(params)}"


def parse_observations(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    obs = payload.get("observations")
    return obs if isinstance(obs, list) else []


def normalize_observation(series_id: str, obs: Dict[str, Any]) -> MacroSeriesPoint:
    val = obs.get("value")
    try:
        value = float(val) if val not in (None, ".", "") else None
    except Exception:
        value = None

    return MacroSeriesPoint(
        ts_utc=utc_now_iso(),
        provider="fred",
        series_id=series_id,
        date=str(obs.get("date")),
        value=value,
        realtime_start=obs.get("realtime_start"),
        realtime_end=obs.get("realtime_end"),
    )


def fetch_series(series_id: str, limit: int) -> List[MacroSeriesPoint]:
    api_key = os.environ.get("FRED_API_KEY")
    url = build_fred_url(series_id, api_key, limit)

    payload = http_get_json(url)
    observations = parse_observations(payload)

    out: List[MacroSeriesPoint] = []
    for o in observations:
        try:
            out.append(normalize_observation(series_id, o))
        except Exception:
            continue

    return out


def write_audit(points: List[MacroSeriesPoint], series_id: str) -> Path:
    log_dir = Path("audit_logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    fname = f"fred_series_{series_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path = log_dir / fname

    payload = {
        "ts_utc": utc_now_iso(),
        "provider": "fred",
        "series_id": series_id,
        "count": len(points),
        "points": [asdict(p) for p in points],
    }

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def main() -> int:
    p = argparse.ArgumentParser(description="FRED Macro Series Adapter (REA)")
    p.add_argument("--series", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--audit", action="store_true")
    args = p.parse_args()

    points = fetch_series(args.series, args.limit)

    # Always print JSON array (never crash)
    print(json.dumps([asdict(p) for p in points], indent=2))

    if args.audit:
        path = write_audit(points, args.series)
        print(f"\nAUDIT_LOG_WRITTEN: {path}")

    # Guidance
    if not os.environ.get("FRED_API_KEY"):
        print("\nNOTE: FRED_API_KEY is not set. FRED may rate-limit or reject some calls.")
        print("Set it in this CMD session like:")
        print("  set FRED_API_KEY=your_fred_key_here")
        print("Then rerun the command.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
