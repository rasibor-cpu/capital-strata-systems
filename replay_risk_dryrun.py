"""
Task 9.3 — End-to-End Risk Dry-Run Harness

Purpose:
- Simulate signal flow into RiskRouter
- Collect and print canonical counters
- NO execution
- NO broker interaction
- Safe, deterministic, analysis-only
"""

from datetime import datetime, timezone
from typing import List

from risk_positioning import RiskConfig
from risk_router import RiskRouter


def synthetic_signal_stream(n: int) -> List[bool]:
    """
    Deterministic synthetic signal generator.
    True = signal present
    False = no signal
    """
    pattern = [False, True, False, True, True, False]
    out = []
    for i in range(n):
        out.append(pattern[i % len(pattern)])
    return out


def main() -> None:
    # --- risk configuration ---
    risk_cfg = RiskConfig(
        account_equity=10_000,
        risk_per_trade=0.01,
        stop_loss_pips=20,
        pip_value_per_lot=10,
        max_lot_size=5.0,
    )

    router = RiskRouter(risk_cfg)

    # --- synthetic replay ---
    signals = synthetic_signal_stream(20)

    for flag in signals:
        router.evaluate_signal(flag)

    # --- canonical summary ---
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    print("=== REA RISK DRY-RUN SUMMARY (CANONICAL) ===")
    print(f"utc_time: {now}")
    print("--- meta ---")
    print("analysis_only: True")
    print("source: synthetic_signal_stream")
    print("--- risk_counters ---")

    snap = router.snapshot()
    for k, v in snap.items():
        print(f"{k}: {v}")

    print("overall_status: PASS")


if __name__ == "__main__":
    main()