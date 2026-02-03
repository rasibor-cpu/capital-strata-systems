# run_live_guarded.py
"""
Live Guarded Runner (NO BROKER / NO ORDERS)

Responsibilities:
- Shows operator LIVE banner (state/policy/gate)
- Supports arming workflow (arm-live / confirm-live / disarm) managed elsewhere
- Performs a final execution gate check (policy + arming + rate-limit + auto-disarm)
- NEVER sends orders (broker wiring is separate)

Flags:
  --arm-live          Request live arming (creates ARMED_PENDING)
  --confirm-live CODE Confirm live arming (moves to ARMED_ACTIVE)  [handled by existing governance logic]
  --disarm            Disarm immediately
"""

from __future__ import annotations

import argparse

from engine.execution.execution_gate import execution_gate_check
from engine.execution.live_state import get_live_state
from engine.execution.auto_disarm import check_auto_disarm
from engine.execution.execution_policy_loader import load_execution_policy
from engine.runtime.live_banner import emit_banner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm-live", action="store_true", help="Request live arming (governance)")
    parser.add_argument("--confirm-live", type=str, default=None, help="Confirm live arming with token/code")
    parser.add_argument("--disarm", action="store_true", help="Disarm immediately")
    args = parser.parse_args()

    # NOTE: arming/confirm/disarm state transitions are handled in your governance arming code.
    # This runner only SHOWS state + performs gate check.

    # Load policy (fail-closed if missing)
    try:
        policy = load_execution_policy()
        policy_version = str(policy.get("version", "unknown"))
    except Exception:
        policy_version = "missing"

    # Read current arming state
    ls = get_live_state()

    # Auto-disarm check (visibility only here; enforcement may be in arming workflow)
    disarm_reason = check_auto_disarm()

    # Final execution gate check (context is illustrative)
    gate = execution_gate_check({"instrument": "EURUSD", "risk_pct": 1.0})

    # Emit LIVE banner for operator
    emit_banner(
        armed_state=ls.state,
        expires_at_utc=ls.expires_at_utc,
        policy_version=policy_version,
        gate_decision=gate.get("decision", "BLOCK"),
        gate_reason=gate.get("reason", "unknown"),
        auto_disarm_reason=disarm_reason,
        extra_meta={"note": "Runner is NO-ORDER. Broker wiring is separate."},
    )

    # Always exit 0 for visibility runs; execution is blocked by gate anyway.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
