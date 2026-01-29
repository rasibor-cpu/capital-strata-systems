from __future__ import annotations

import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Optional

from feeds.fx_feed_base import FXBar1m
from feeds.fx_replay_feed import ReplayFXFeed
from feeds.fx_oanda_feed import OandaFXFeed
from feeds.fx_composite_feed import CompositeFXFeed


# -------------------------
# Helpers
# -------------------------
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


# -------------------------
# Main runner
# -------------------------
def main() -> None:
    print("=" * 72)
    print("REA Capital — FX Live Prompt Runner (Prompt-Only)")
    print("UTC Now:", datetime.now(timezone.utc).isoformat())
    print("CWD:", os.getcwd())
    print("=" * 72)

    # --- Load signal builder
    try:
        from signals.vwap_mean_reversion import build_vwap_prompt_default_eps
    except Exception as e:
        print("ERROR: Cannot import VWAP prompt builder:", e)
        return

    # --- Provider selection
    provider = env("FX_PROVIDER", "replay")
    instrument = env("FX_INSTRUMENT", "EUR_USD")

    replay_csv = env("REPLAY_CSV_PATH", "data_fx\\EUR_USD_1m.csv")
    replay_speed = float(env("REPLAY_SPEED", "200") or "200")

    # --- Build feed
    if provider == "replay":
        feed = ReplayFXFeed(
            csv_path=replay_csv,
            instrument=instrument,
            speed=replay_speed,
        )
    elif provider == "oanda":
        feed = OandaFXFeed(
            env=env("OANDA_ENV", "practice"),
            api_token=env("OANDA_API_TOKEN"),
            account_id=env("OANDA_ACCOUNT_ID"),
            instrument=instrument,
            granularity="M1",
            poll_s=5.0,
        )
    else:
        feed = CompositeFXFeed(
            primary=OandaFXFeed(
                env=env("OANDA_ENV", "practice"),
                api_token=env("OANDA_API_TOKEN"),
                account_id=env("OANDA_ACCOUNT_ID"),
                instrument=instrument,
                granularity="M1",
                poll_s=5.0,
            ),
            fallback=ReplayFXFeed(
                csv_path=replay_csv,
                instrument=instrument,
                speed=replay_speed,
            ),
        )

    # --- Connect feed
    feed.connect()
    print(f"[OK] FX feed connected: provider={provider}, instrument={instrument}")

    # --- Rolling window
    window: Deque[FXBar1m] = deque(maxlen=5)
    eps_pct = 0.0001
    prompts = 0

    # -------------------------
    # MAIN LOOP (this was missing before)
    # -------------------------
    while True:
        bar = feed.next_bar(timeout_s=10.0)

        if bar is None:
            time.sleep(0.1)
            continue

        print("[BAR]", bar)

        window.append(bar)

        if len(window) < 5:
            continue

        vwap = compute_vwap(window)
        if vwap is None:
            continue

        prompt = build_vwap_prompt_default_eps(
            price=bar.c,
            vwap=vwap,
            pct=eps_pct,
            extra={
                "instrument": instrument,
                "as_of_utc": bar.ts_utc,
            },
        )

        prompts += 1
        print(f"[PROMPT {prompts}]", prompt)


if __name__ == "__main__":
    main()