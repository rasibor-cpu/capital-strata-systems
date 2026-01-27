"""
Module 3 Demo Runner (Prompt-only) — CLEAN + AUTHORITATIVE (FIXED)
------------------------------------------------------------------
Purpose:
- Verify Module 3 prompt generation
- Show regime gate behavior clearly
- DEV-only override by wrapping the *regime_allows()* method safely
- No engine edits required
- Prompt-only (NO execution, NO risk)

USAGE (Windows CMD):
  python run_module3_demo.py
  set DEV_FORCE_ALLOW=1 && python run_module3_demo.py
  set MIN_BARS=1 && set VWAP_EPS_PCT=0 && set DEV_FORCE_ALLOW=1 && python run_module3_demo.py
"""

import os
import json
from engine_loop import EngineLoop, EngineConfig
import replay_csv


# =========================
# ENV / INPUTS
# =========================
CSV_PATH = os.getenv("CSV_PATH", "sample_spy_1m_long.csv")

VWAP_WINDOW_BARS = int(os.getenv("VWAP_WINDOW_BARS", "5"))
MIN_BARS = int(os.getenv("MIN_BARS", "5"))
VWAP_EPS_PCT = float(os.getenv("VWAP_EPS_PCT", "0.0001"))

DEV_FORCE_ALLOW = os.getenv("DEV_FORCE_ALLOW", "0") == "1"
PRINT_PROMPTS = os.getenv("PRINT_PROMPTS", "1") == "1"
PRINT_SAMPLE_PROMPT = os.getenv("PRINT_SAMPLE_PROMPT", "1") == "1"


# =========================
# HELPERS
# =========================
def extract_prompt(snapshot):
    if not isinstance(snapshot, dict):
        return None
    for k in ("prompt", "prompt_text", "prompt_payload"):
        if snapshot.get(k):
            return snapshot[k]
    return None


def apply_dev_force_allow(engine: EngineLoop):
    """
    DEV ONLY.
    If engine has a callable regime_allows(), wrap it to always return True.
    This avoids breaking code that expects regime_allows() to be callable.
    """
    if hasattr(engine, "regime_allows") and callable(getattr(engine, "regime_allows")):
        original = engine.regime_allows

        def forced_true():
            return True

        engine.regime_allows = forced_true  # monkey-patch callable
        return True, original
    return False, None


# =========================
# MAIN
# =========================
def main():
    print("=== REA Capital :: Module 3 Demo (Prompt-only) ===")
    print(f"CSV_PATH={CSV_PATH}")
    print(f"VWAP_WINDOW_BARS={VWAP_WINDOW_BARS}")
    print(f"MIN_BARS={MIN_BARS}")
    print(f"VWAP_EPS_PCT={VWAP_EPS_PCT}")
    print(f"DEV_FORCE_ALLOW={int(DEV_FORCE_ALLOW)}")
    print("-" * 72)

    ecfg = EngineConfig(
        symbol="SPY",
        vwap_window_bars=VWAP_WINDOW_BARS,
        min_bars_before_signals=MIN_BARS,
        vwap_eps_pct=VWAP_EPS_PCT,
        print_prompts=PRINT_PROMPTS,
    )

    engine = EngineLoop(ecfg)

    if DEV_FORCE_ALLOW:
        ok, _ = apply_dev_force_allow(engine)
        if ok:
            print("[DEV] regime_allows() forced to True (callable monkey-patch)")
        else:
            print("[DEV] regime_allows() not found/callable (unexpected)")

    rcfg = replay_csv.CSVReplayConfig(csv_path=CSV_PATH, symbol="SPY")

    prompts_seen = 0
    sample_prompt = None

    original_on_bar = engine.on_bar

    def wrapped_on_bar(bar, **kwargs):
        nonlocal prompts_seen, sample_prompt
        snap = original_on_bar(bar, **kwargs)
        p = extract_prompt(snap)
        if p:
            prompts_seen += 1
            if sample_prompt is None:
                sample_prompt = p
        return snap

    engine.on_bar = wrapped_on_bar

    result = replay_csv.replay(rcfg, engine)

    print("-" * 72)
    print("=== Replay complete ===")

    if isinstance(result, dict):
        for k in sorted(result):
            print(f"{k}: {result[k]}")

    print(f"prompts_seen_by_wrapper: {prompts_seen}")

    if PRINT_SAMPLE_PROMPT and sample_prompt is not None:
        print("-" * 72)
        print("=== SAMPLE PROMPT (FIRST) ===")
        if isinstance(sample_prompt, (dict, list)):
            print(json.dumps(sample_prompt, indent=2))
        else:
            print(str(sample_prompt)[:2000])

    print("-" * 72)


if __name__ == "__main__":
    main()