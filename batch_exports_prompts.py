"""
batch_export_prompts.py — Batch Prompt Export (Prompt-only)
----------------------------------------------------------
Reads a CSV (default: sample_spy_1m_long.csv) through replay_csv.replay
and writes normalized prompts to a JSONL file (one JSON object per line).

No execution. Prompt-only.

Usage (CMD):
  python batch_export_prompts.py
  set CSV_PATH=sample_spy_1m_long.csv && set OUT_PATH=prompts.jsonl && python batch_export_prompts.py
  set DEV_FORCE_ALLOW=1 && python batch_export_prompts.py
"""

import os
import json
from engine_loop import EngineConfig, EngineLoop
import replay_csv
from utils.prompt_export import normalize_prompt

CSV_PATH = os.getenv("CSV_PATH", "sample_spy_1m_long.csv")
OUT_PATH = os.getenv("OUT_PATH", "prompts.jsonl")
DEV_FORCE_ALLOW = os.getenv("DEV_FORCE_ALLOW", "0") == "1"

# Keep engine output quiet for batch runs
PRINT_PROMPTS = os.getenv("PRINT_PROMPTS", "0") == "1"

# Engine tuning knobs (defaults are safe)
VWAP_WINDOW_BARS = int(os.getenv("VWAP_WINDOW_BARS", "5"))
MIN_BARS = int(os.getenv("MIN_BARS", "5"))
VWAP_EPS_PCT = float(os.getenv("VWAP_EPS_PCT", "0.0001"))


def main():
    print("=== Batch Prompt Export (JSONL) ===")
    print(f"CSV_PATH={CSV_PATH}")
    print(f"OUT_PATH={OUT_PATH}")
    print(f"DEV_FORCE_ALLOW={int(DEV_FORCE_ALLOW)}")

    ecfg = EngineConfig(
        symbol="SPY",
        vwap_window_bars=VWAP_WINDOW_BARS,
        min_bars_before_signals=MIN_BARS,
        vwap_eps_pct=VWAP_EPS_PCT,
        print_prompts=PRINT_PROMPTS,
    )

    engine = EngineLoop(ecfg)

    # DEV-only: force regime allow without modifying engine source
    if DEV_FORCE_ALLOW:
        # engine.regime_allows is callable -> patch it safely
        engine.regime_allows = (lambda: True)

    rcfg = replay_csv.CSVReplayConfig(csv_path=CSV_PATH, symbol="SPY")

    prompts_written = 0

    # Wrap on_bar to capture prompts and write normalized output
    original_on_bar = engine.on_bar

    def wrapped_on_bar(bar, **kwargs):
        nonlocal prompts_written
        snap = original_on_bar(bar, **kwargs)
        if isinstance(snap, dict) and snap.get("signal"):
            norm = normalize_prompt(snap)
            if norm and norm.get("signal"):
                with open(OUT_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(norm) + "\n")
                prompts_written += 1
        return snap

    engine.on_bar = wrapped_on_bar

    # Clear existing output file first
    if os.path.exists(OUT_PATH):
        os.remove(OUT_PATH)

    # Run replay
    result = replay_csv.replay(rcfg, engine)

    print("=== Replay complete ===")
    if isinstance(result, dict):
        for k in sorted(result):
            print(f"{k}: {result[k]}")
    print(f"prompts_written: {prompts_written}")
    print(f"Output file: {OUT_PATH}")


if __name__ == "__main__":
    main()