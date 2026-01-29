from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

from feeds.fx_replay_feed import ReplayFXFeed
from feeds.fx_feed_base import FXBar1m


@dataclass
class PairConfig:
    instrument: str
    csv_path: str
    speed: float = 200.0


def compute_vwap(window: Deque[FXBar1m]) -> Optional[float]:
    pv = 0.0
    vol = 0.0
    for b in window:
        v = float(b.v) if b.v else 0.0
        pv += float(b.c) * v
        vol += v
    return pv / vol if vol > 0 else None


def main() -> int:
    print("=" * 72)
    print("REA Capital — FX Multi-Pair Replay Runner (Prompt-Only)")
    print("UTC Now:", datetime.now(timezone.utc).isoformat())
    print("CWD:", os.getcwd())
    print("=" * 72)

    # Optional audit
    audit = None
    try:
        from engine.security.access_audit_log import AccessAuditLogger  # type: ignore
        audit = AccessAuditLogger()
        audit.write("session_start", {"runner": "run_fx_pairs_replay"})
    except Exception:
        audit = None

    # Prompt builder
    try:
        from signals.vwap_mean_reversion import build_vwap_prompt_default_eps  # type: ignore
    except Exception as e:
        print("ERROR: cannot import VWAP prompt builder:", repr(e))
        return 2

    # Pair list (3 majors by default)
    # For now we can point all of them to the same replay CSV to test plumbing.
    # Later we swap to real EURUSD/GBPUSD/USDJPY CSVs without changing code.
    base_csv = os.getenv("REPLAY_CSV_PATH", "sample_spy_1m_long.csv").strip() or "sample_spy_1m_long.csv"
    speed = float(os.getenv("REPLAY_SPEED", "200") or "200")

    pairs: List[PairConfig] = [
        PairConfig("EUR_USD", base_csv, speed),
        PairConfig("GBP_USD", base_csv, speed),
        PairConfig("USD_JPY", base_csv, speed),
    ]

    feeds: Dict[str, ReplayFXFeed] = {}
    windows: Dict[str, Deque[FXBar1m]] = {}
    done: Dict[str, bool] = {}

    for p in pairs:
        feeds[p.instrument] = ReplayFXFeed(csv_path=p.csv_path, instrument=p.instrument, speed=p.speed)
        windows[p.instrument] = deque(maxlen=5)
        done[p.instrument] = False

    for f in feeds.values():
        f.connect()

    print("[OK] Feeds connected:", ", ".join(feeds.keys()))
    if audit:
        audit.write("fx_pairs_start", {"pairs": [p.instrument for p in pairs], "csv": base_csv, "speed": speed})

    prompts = 0
    eps_pct = 0.0001

    try:
        # Round-robin each pair; stop when all feeds exhausted
        while True:
            all_done = True

            for inst, feed in feeds.items():
                if done[inst]:
                    continue

                bar = feed.next_bar(timeout_s=0.1)
                if bar is None:
                    done[inst] = True
                    continue

                all_done = False

                w = windows[inst]
                w.append(bar)
                if len(w) < 5:
                    continue

                vwap = compute_vwap(w)
                if vwap is None:
                    continue

                prompt = build_vwap_prompt_default_eps(
                    price=float(bar.c),
                    vwap=float(vwap),
                    pct=float(eps_pct),
                    extra={
                        "instrument": inst,
                        "as_of_utc": bar.ts_utc.isoformat() if hasattr(bar.ts_utc, "isoformat") else str(bar.ts_utc),
                        "provider": "replay",
                        "csv": feed.csv_path,
                    },
                )

                prompts += 1
                print(prompt)

                if audit:
                    audit.write("fx_prompt", {"instrument": inst, "count": prompts})

            if all_done:
                break

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user.")
    finally:
        for f in feeds.values():
            f.close()
        if audit:
            audit.write("session_end", {"prompts_generated": prompts})

    print(f"\nDone. Prompts generated: {prompts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())