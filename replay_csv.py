from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional
import csv

from engine_loop import Bar, EngineLoop


def _parse_ts_utc(s: str) -> datetime:
    s = (s or "").strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class CSVReplayConfig:
    csv_path: str
    max_rows: Optional[int] = None
    print_every: int = 25


def iter_csv_bars(cfg: CSVReplayConfig, symbol: str) -> Iterator[Bar]:
    count = 0
    with open(cfg.csv_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = _parse_ts_utc(row.get("ts_utc", ""))
            c = float(row.get("c") or row.get("close") or 0.0)

            v_raw = row.get("v")
            if v_raw is None:
                v_raw = row.get("volume")
            v = float(v_raw or 0.0)

            yield Bar(ts_utc=ts, symbol=symbol, close=c, volume=v)

            count += 1
            if cfg.max_rows is not None and count >= cfg.max_rows:
                return


def replay(cfg: CSVReplayConfig, engine: EngineLoop) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "bars_1m": 0,
        "safe_mode_issues": 0,
        "last_snap": None,
    }

    for bar in iter_csv_bars(cfg, engine.cfg.symbol):
        snap = engine.on_bar(bar)
        stats["bars_1m"] += 1

        if snap is not None:
            stats["last_snap"] = snap

        if cfg.print_every and (stats["bars_1m"] % cfg.print_every == 0):
            print(f"[REPLAY] bars_1m={stats['bars_1m']}")

    return stats