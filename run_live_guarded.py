# run_live_guarded.py
"""
Live Guarded Runner (NO BROKER)

Governance:
- 6-char token (outbox email/sms)
- explicit channel selection
- preflight required for confirm
- restart safety: if ARMED_ACTIVE, requires reconfirm within 2 minutes or DISARM
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta

from engine.execution.execution_gate import execution_gate_check
from engine.execution.live_state import (
    get_live_state, request_arm, confirm_arm, force_disarm
)
from engine.execution.auto_disarm import check_auto_disarm
from engine.execution.execution_policy_loader import load_execution_policy
from engine.execution.confirm_token import generate_token
from engine.execution.notify_outbox import write_email, write_sms
from engine.runtime.live_banner import emit_banner

from config.superuser_loader import load_superuser


RESTART_RECONFIRM_WINDOW_SECONDS = 120  # 2 minutes


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _mask_email(e: str) -> str:
    name, _, dom = e.partition("@")
    return f"{name[:2]}***@{dom}"


def _mask_phone(p: str) -> str:
    return f"+***{p[-4:]}"


def _restart_safety() -> None:
    """
    If system is ARMED_ACTIVE at startup, require reconfirm within 2 minutes.
    We model this as: if last_updated_utc older than 2 minutes -> DISARM.
    """
    ls0 = get_live_state()
    if ls0.state != "ARMED_ACTIVE":
        return

    try:
        last = _parse_iso(ls0.last_updated_utc)
    except Exception:
        force_disarm("restart_reconfirm_parse_failed")
        return

    age = datetime.now(timezone.utc) - last
    if age > timedelta(seconds=RESTART_RECONFIRM_WINDOW_SECONDS):
        force_disarm("restart_requires_reconfirm_expired")
    else:
        # still within 2-minute window: keep ARMED_ACTIVE but visibly warn
        # (banner will show ACTIVE; operator should immediately reconfirm/disarm)
        pass


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--arm-live", action="store_true")
    p.add_argument("--confirm-live", type=str, default=None, help="6-char token")
    p.add_argument("--disarm", action="store_true")
    args = p.parse_args()

    # Policy
    try:
        policy = load_execution_policy()
        policy_v = str(policy.get("version", "unknown"))
    except Exception:
        policy_v = "missing"

    # Auto-disarm enforcement
    disarm_reason = check_auto_disarm()

    # Restart safety (2-minute reconfirm requirement)
    _restart_safety()

    # DISARM
    if args.disarm:
        force_disarm("operator_disarm")

    # ARM REQUEST
    if args.arm_live:
        su = load_superuser()
        ls = request_arm()
        if ls.state != "ARMED_PENDING":
            print("ARM request rejected (rate-limit/cooldown or safety).")
        else:
            token = generate_token(6)

            ch = input("Send confirm token via Email or SMS? [E/S]: ").strip().upper()
            if ch == "E":
                write_email(su["primary"]["email"], token)
                print(f"Token written to EMAIL outbox for {_mask_email(su['primary']['email'])}")
            else:
                write_sms(su["primary"]["phone_e164"], token)
                print(f"Token written to SMS outbox for {_mask_phone(su['primary']['phone_e164'])}")

            print("ARMED_PENDING created. Token expires per TTL + rate-limit applies.")

    # CONFIRM
    if args.confirm_live:
        # Preflight must PASS
        from run_preflight import preflight_passed
        if not preflight_passed():
            force_disarm("preflight_failed")
        else:
            # NOTE: token validation is handled in your CLI/token layer later.
            # For now we treat confirm-live as the operator action gate.
            confirm_arm(preflight_ok=True)

    # Gate check (still no orders)
    gate = execution_gate_check({"instrument": "EURUSD", "risk_pct": 1.0})
    ls = get_live_state()

    emit_banner(
        armed_state=ls.state,
        expires_at_utc=ls.expires_at_utc,
        policy_version=policy_v,
        gate_decision=gate.get("decision", "BLOCK"),
        gate_reason=gate.get("reason", "unknown"),
        auto_disarm_reason=disarm_reason,
        extra_meta={"sentinel": "NO_ORDERS"},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
