# ============================================================
# REA FX PAIRS REPLAY v4 — FXRULES CARRY (RESEARCH ONLY)
# Prompt-only engine. NO execution. NO broker calls.
# ============================================================

import csv
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Iterator

from indicators.bollinger import compute_bollinger

# -----------------------------
# Helpers
# -----------------------------

def to_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def parse_ts(x: str) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0

# -----------------------------
# Data Structures
# -----------------------------

@dataclass
class Tick:
    ts: float
    pair: str
    mid: float

@dataclass
class Bar:
    ts_open: float
    ts_close: float
    pair: str
    close: float
    vwap: float
    n: int

# -----------------------------
# Bar Builder
# -----------------------------

class BarBuilder:
    def __init__(self, tf_sec: int):
        self.tf = tf_sec
        self.buf: Dict[str, List[Tick]] = {}

    def push(self, t: Tick):
        bucket = int(t.ts // self.tf)
        buf = self.buf.setdefault(t.pair, [])

        if not buf:
            buf.append(t)
            return None

        cur_bucket = int(buf[0].ts // self.tf)
        if bucket == cur_bucket:
            buf.append(t)
            return None

        # close bar
        mids = [x.mid for x in buf]
        bar = Bar(
            ts_open=buf[0].ts,
            ts_close=buf[-1].ts,
            pair=t.pair,
            close=mids[-1],
            vwap=sum(mids) / len(mids),
            n=len(mids),
        )

        # reset buffer
        self.buf[t.pair] = [t]
        return bar

# -----------------------------
# CSV Loader
# -----------------------------

def load_ticks(csv_path: str) -> Iterator[Tick]:
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pair = row.get("pair", "").replace("/", "")
            mid = to_float(row.get("mid"))
            ts = parse_ts(row.get("timestamp"))
            if pair and mid > 0 and ts > 0:
                yield Tick(ts, pair, mid)

# -----------------------------
# Main Runner
# -----------------------------

def run():
    csv_path = os.environ.get("REA_FX_CSV", "data/fx_pairs.csv")
    out_path = "out/fx_prompts.txt"
    os.makedirs("out", exist_ok=True)

    bb1 = BarBuilder(60)
    bb5 = BarBuilder(300)

    BB_PERIOD = 20
    price_buf: Dict[str, List[float]] = {}

    bars_1m = bars_5m = allow = block = prompts = 0

    with open(out_path, "w", encoding="utf-8") as out:
        for t in load_ticks(csv_path):

            b1 = bb1.push(t)
            if b1:
                bars_1m += 1

            b5 = bb5.push(t)
            if not b5:
                continue

            bars_5m += 1
            buf = price_buf.setdefault(b5.pair, [])
            buf.append(b5.close)

            if len(buf) < BB_PERIOD:
                block += 1
                continue

            allow += 1
            bb = compute_bollinger(buf, BB_PERIOD, 2.0)
            prompts += 1

            out.write(f"PAIR={b5.pair}\n")
            out.write(f"close={b5.close:.6f} vwap={b5.vwap:.6f}\n")
            out.write(f"bollinger_mid={bb.mid:.6f}\n")
            out.write(f"bollinger_upper={bb.upper:.6f}\n")
            out.write(f"bollinger_lower={bb.lower:.6f}\n")
            out.write(f"bollinger_state={bb.state.name}\n")
            out.write("-" * 72 + "\n")

            time.sleep(0.01)  # throttle (research only)

    print("\nREA FX Runner Summary")
    print("-" * 72)
    print(f"bars_1m: {bars_1m}")
    print(f"bars_5m: {bars_5m}")
    print(f"regime_allow: {allow}")
    print(f"regime_block: {block}")
    print(f"prompts_generated: {prompts}")
    print("-" * 72)

# -----------------------------
# Entrypoint
# -----------------------------

if __name__ == "__main__":
    run()
