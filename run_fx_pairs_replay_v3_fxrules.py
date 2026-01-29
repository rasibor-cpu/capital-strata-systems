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


# -------------------------------------------------
# FX Carry / Swap Metadata (PROMPT-ONLY)
# -------------------------------------------------
@dataclass(frozen=True)
class FXCarryInfo:
    base: str
    quote: str
    carry_bias: str          # "LONG", "SHORT", "NEUTRAL"
    swap_long_note: str
    swap_short_note: str
    rollover_note: str


FX_CARRY_TABLE: Dict[str, FXCarryInfo] = {
    "EUR_USD": FXCarryInfo(
        base="EUR",
        quote="USD",
        carry_bias="SHORT",  # USD > EUR historically
        swap_long_note="Typically negative carry when long EURUSD",
        swap_short_note="Typically positive carry when short EURUSD",
        rollover_note="Triple swap usually applied mid-week",
    ),
    "GBP_USD": FXCarryInfo(
        base="GBP",
        quote="USD",
        carry_bias="NEUTRAL",
        swap_long_note="Carry fluctuates; regime-dependent",
        swap_short_note="Carry fluctuates; regime-dependent",
        rollover_note="Triple swap usually applied mid-week",
    ),
    "USD_JPY": FXCarryInfo(
        base="USD",
        quote="JPY",
        carry_bias="LONG",  # USD > JPY historically
        swap_long_note="Typically positive carry when long USDJPY",
        swap_short_note="Typically negative carry when short USDJPY",
        rollover_note="Triple swap usually applied mid-week",
    ),
}


# -------------------------------------------------
# Pair config
# -------------------------------------------------
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


# -------------------------------------------------
# MAIN
# -------------------------------------------------
def main() -> None:
    print("=" * 72)
    print("REA Capital — FX Multi-Pair Replay + FX Rules + Carry (Prompt-Only)")
    print("UTC Now:", datetime.now(timezone.utc).isoformat())
    print("CWD:", os.getcwd())
    print("=" * 72)

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

    pair_prompts: Dict[str, int] = {p.instrument: 0 for p in pairs}
    pair_blocks: Dict[str, int] = {p.instrument: 0 for p in pairs}

    for p in pairs:
        path = p.csv_path if os.path.exists(p.csv_path) else eur
        feeds[p.instrument] = ReplayFXFeed(
            csv_path=path,
            instrument=p.instrument,
            speed=p.speed,
        )
        windows[p.instrument] = deque(maxlen=5)
        done[p.instrument] = False

    for f in feeds.values():
        f.connect()

    print("[OK] Feeds connected:", ", ".join(feeds.keys()))

    fx_cfg = FXRuleConfig()
    eps_pct = 0.0001

    total_prompts = 0
    total_blocks = 0

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

                decision = fx_rules_allow(ts_utc=bar.ts_utc, cfg=fx_cfg)
                if not decision["allow"]:
                    total_blocks += 1
                    pair_blocks[inst] += 1
                    continue

                w = windows[inst]
                w.append(bar)
                if len(w) < 5:
                    continue

                vwap = compute_vwap(w)
                if vwap is None:
                    continue

                carry = FX_CARRY_TABLE.get(inst)

                prompt = build_vwap_prompt_default_eps(
                    price=float(bar.c),
                    vwap=float(vwap),
                    pct=float(eps_pct),
                    extra={
                        "instrument": inst,
                        "as_of_utc": bar.ts_utc,
                        "provider": "replay",
                        "session": decision["session"],
                        "fx_rules_reason": decision["reason"],
                        "carry_bias": carry.carry_bias if carry else "UNKNOWN",
                        "swap_long_note": carry.swap_long_note if carry else None,
                        "swap_short_note": carry.swap_short_note if carry else None,
                        "rollover_note": carry.rollover_note if carry else None,
                    },
                )

                total_prompts += 1
                pair_prompts[inst] += 1
                print(f"[{inst} PROMPT {total_prompts}]", prompt)

            if all_done:
                break

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user.")

    print("\n" + "=" * 72)
    print(f"Done. Prompts generated: {total_prompts} | FX-rule blocks: {total_blocks}")
    print(f"Per-pair prompts: {pair_prompts}")
    print(f"Per-pair FX-rule blocks: {pair_blocks}")
    print("=" * 72)


if __name__ == "__main__":
    main()