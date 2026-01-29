from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Deque, Dict, Optional, List

from feeds.fx_replay_feed import ReplayFXFeed
from feeds.fx_feed_base import FXBar1m
from regime.fx_rules import FXRuleConfig, fx_rules_allow


@dataclass
class PairCfg:
    instrument: str
    csv_path: str
    speed: float


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def compute_vwap(window: Deque[FXBar1m]) -> Optional[float]:
    pv = 0.0
    vol = 0.0
    for b in window:
        v = float(b.v) if b.v else 0.0
        pv += float(b.c) * v
        vol += v
    return pv / vol if vol > 0 else None


def main() -> None:
    print("=" * 72)
    print("REA Capital — FX Multi-Pair Replay + FX Rules + Counters (Prompt-Only)")
    print("UTC Now:", datetime.now(timezone.utc).isoformat())
    print("CWD:", os.getcwd())
    print("=" * 72)

    # prompt builder
    try:
        from signals.vwap_mean_reversion import build_vwap_prompt_default_eps
    except Exception as e:
        print("ERROR: Cannot import VWAP prompt builder:", e)
        return

    speed = float(env("REPLAY_SPEED", "200") or "200")

    eur = env("EUR_USD_CSV", r"data_fx\EUR_USD_1m.csv")
    gbp = env("GBP_USD_CSV", r"data_fx\GBP_USD_1m.csv")
    jpy = env("USD_JPY_CSV", r"data_fx\USD_JPY_1m.csv")

    pairs: List[PairCfg] = [
        PairCfg("EUR_USD", eur, speed),
        PairCfg("GBP_USD", gbp, speed),
        PairCfg("USD_JPY", jpy, speed),
    ]

    feeds: Dict[str, ReplayFXFeed] = {}
    windows: Dict[str, Deque[FXBar1m]] = {}
    done: Dict[str, bool] = {}

    # Counters
    pair_prompts: Dict[str, int] = {p.instrument: 0 for p in pairs}
    pair_blocks: Dict[str, int] = {p.instrument: 0 for p in pairs}

    # connect feeds (fallback to EUR file if missing so plumbing still runs)
    for p in pairs:
        path = p.csv_path
        if not os.path.exists(path):
            path = eur
        feeds[p.instrument] = ReplayFXFeed(csv_path=path, instrument=p.instrument, speed=p.speed)
        windows[p.instrument] = deque(maxlen=5)
        done[p.instrument] = False

    for f in feeds.values():
        f.connect()

    print("[OK] Feeds connected:", ", ".join(feeds.keys()))
    print("[INFO] CSV paths:", {k: v.csv_path for k, v in feeds.items()})

    fx_cfg = FXRuleConfig()  # defaults: allow London/NY/Overlap; block rollover + placeholder news

    eps_pct = 0.0001
    prompts = 0
    blocked = 0

    try:
        while True:
            all_done = True

            for inst, feed in feeds.items():
                if done[inst]:
                    continue

                bar = feed.next_bar(timeout_s=0.05)
                if bar is None:
                    done[inst] = True
                    continue

                all_done = False

                # FX RULES GATE (before VWAP)
                decision = fx_rules_allow(ts_utc=bar.ts_utc, cfg=fx_cfg)
                if not decision["allow"]:
                    blocked += 1
                    pair_blocks[inst] += 1
                    # lightweight periodic logging
                    if blocked % 100 == 0:
                        print(f"[FX_RULES BLOCK] total={blocked} per_pair={pair_blocks} last={decision}")
                    continue

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
                        "as_of_utc": bar.ts_utc,
                        "provider": "replay",
                        "csv": feed.csv_path,
                        "session": decision["session"],
                        "fx_rules_reason": decision["reason"],
                    },
                )

                prompts += 1
                pair_prompts[inst] += 1
                print(f"[{inst} PROMPT {prompts}]", prompt)

            if all_done:
                break

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user.")

    print("\n" + "=" * 72)
    print(f"Done. Prompts generated: {prompts} | FX-rule blocks: {blocked}")
    print(f"Per-pair prompts: {pair_prompts}")
    print(f"Per-pair FX-rule blocks: {pair_blocks}")
    print("=" * 72)


if __name__ == "__main__":
    main()