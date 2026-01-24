from __future__ import annotations
import csv
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Iterator, Dict, Any

from data.models import Bar
from engine_loop import REACapitalEngineLoop, EngineConfig


@dataclass
class CSVReplayConfig:
    """
    CSV format (required headers):
      ts_utc,o,h,l,c,v

    ts_utc must be ISO-8601, e.g.:
      2026-01-22T14:45:00Z
    or
      2026-01-22T14:45:00+00:00
    """
    csv_path: str
    max_rows: Optional[int] = None
    print_every: int = 5
    print_prompts: bool = True
    print_regime: bool = True

    # Simulate arrival time as bar_close + N seconds (so validator passes)
    arrival_delay_seconds: int = 20


def _parse_ts_utc(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError("ts_utc must be timezone-aware (include Z or +00:00).")
    return dt.astimezone(timezone.utc)


def iter_csv_bars(cfg: CSVReplayConfig, symbol: str) -> Iterator[Bar]:
    with open(cfg.csv_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        required = {"ts_utc", "o", "h", "l", "c", "v"}
        if not required.issubset(set(r.fieldnames or [])):
            raise ValueError(f"CSV must contain headers: {sorted(required)}")

        count = 0
        for row in r:
            ts = _parse_ts_utc(row["ts_utc"])
            o = float(row["o"])
            h = float(row["h"])
            l = float(row["l"])
            c = float(row["c"])
            v = float(row.get("v") or 0.0)

            yield Bar(symbol=symbol, timeframe="1m", ts=ts, o=o, h=h, l=l, c=c, v=v)

            count += 1
            if cfg.max_rows is not None and count >= cfg.max_rows:
                return


def replay(cfg: CSVReplayConfig, engine: REACapitalEngineLoop) -> Dict[str, Any]:
    stats = {
        "bars_1m": 0,
        "bars_5m": 0,
        "safe_mode_issues": 0,
        "regime_allow": 0,
        "regime_block": 0,
        "prompts_queued": 0,
        "last_regime": None,
    }

    for bar in iter_csv_bars(cfg, engine.cfg.symbol):
        # Simulate that we received the bar shortly after it closes:
        # bar.ts is open time; close is +1 minute.
        received_at = (bar.ts + timedelta(minutes=1) + timedelta(seconds=cfg.arrival_delay_seconds))

        snap = engine.on_bar_1m(bar, received_at_utc=received_at)
        stats["bars_1m"] += 1

        if not snap["ok_1m"] and snap["issue"]:
            stats["safe_mode_issues"] += 1
            print(f"[DATA ISSUE] {snap['issue']['code']} | {snap['issue']['message']}")

        if snap.get("bar5m_created"):
            stats["bars_5m"] += 1

        if snap.get("regime") is not None:
            stats["last_regime"] = snap["regime"]
            if cfg.print_regime:
                print(f"[REGIME] {snap['regime']['decision']} | {', '.join(snap['regime']['reasons'])}")

            if snap["regime"]["decision"] == "ALLOW":
                stats["regime_allow"] += 1
            else:
                stats["regime_block"] += 1

        if snap.get("prompt_queued"):
            stats["prompts_queued"] += 1
            if cfg.print_prompts and snap.get("prompt_summary"):
                print("\n" + snap["prompt_summary"] + "\n")

        if cfg.print_every and stats["bars_1m"] % cfg.print_every == 0:
            elig = snap.get("eligibility", {})
            print(
                f"[{stats['bars_1m']} bars] "
                f"5m={stats['bars_5m']} "
                f"data_ok={elig.get('data_ok')} "
                f"time_ok={elig.get('time_ok')} "
                f"queue_pending={snap.get('queue_pending_count')}"
            )

    return stats


if __name__ == "__main__":
    cfg = CSVReplayConfig(
        csv_path="sample_spy_1m.csv",
        max_rows=None,
        print_every=5,
        print_prompts=True,
        print_regime=True,
        arrival_delay_seconds=20,
    )

    engine = REACapitalEngineLoop(EngineConfig(symbol="SPY"))
    results = replay(cfg, engine)

    print("\n=== REPLAY SUMMARY ===")
    for k, v in results.items():
        print(f"{k}: {v}")
