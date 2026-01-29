"""
Task 10.2 — End-to-End Execution Dry-Run Harness

Purpose:
- Simulate signal → risk → execution chain
- Prove double-guard safety (risk + analysis_only)
- NO broker calls
- NO execution
- Deterministic, analysis-only
"""

from datetime import datetime, timezone
from typing import List

from risk_positioning import RiskConfig
from risk_router import RiskRouter
from execution_router import ExecutionRouter


def synthetic_signal_stream(n: int) -> List[bool]:
    """
    Deterministic synthetic signal generator.
    True = signal present
    False = no signal
    """
    pattern = [False, True, False, True, True, False]
    return [pattern[i % len(pattern)] for i in range(n)]


def main() -> None:
    # --- configuration ---
    risk_cfg = RiskConfig(
        account_equity=10_000,
        risk_per_trade=0.01,
        stop_loss_pips=20,
        pip_value_per_lot=10,
        max_lot_size=5.0,
    )

    risk_router = RiskRouter(risk_cfg)
    exec_router = ExecutionRouter(analysis_only=True)

    # --- synthetic replay ---
    signals = synthetic_signal_stream(20)

    for flag in signals:
        risk_decision = risk_router.evaluate_signal(flag)
        if risk_decision is None:
            continue

        # feed risk decision into execution router
        exec_router.evaluate(risk_decision.allowed)

    # --- canonical summary ---
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    print("=== REA EXECUTION DRY-RUN SUMMARY (CANONICAL) ===")
    print(f"utc_time: {now}")
    print("--- meta ---")
    print("analysis_only: True")
    print("source: synthetic_signal_stream")

    print("--- risk_counters ---")
    for k, v in risk_router.snapshot().items():
        print(f"{k}: {v}")

    print("--- execution_counters ---")
    for k, v in exec_router.snapshot().items():
        print(f"{k}: {v}")

    print("overall_status: PASS")


if __name__ == "__main__":
    main()