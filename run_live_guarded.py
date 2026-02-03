# run_live_guarded.py
"""
Live Guarded Runner (NO BROKER)

Governance:
- 6-char token (A-Z0-9)
- explicit channel selection (email/sms) -> runtime outbox
- token must validate to confirm live (fail-closed + DISARM on mismatch)
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
from engine.execution.confirm_registry import (
    write_pending_token, validate_token, clear_pending_token
)
from engine.runtime.live_banner import emit_banner

from config.superuser_loader import load_superuser


RESTART_RECONFIRM_WINDOW_SECONDS = 120  # 2 minutes
CONFIRM_TOKEN_TTL_SECONDS = 900         # 15 minutes (adjust later if desired)


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
    If last_updated_utc older than 2 minutes -> DISARM (fail-closed).
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
        clear_pending_token()
        force_disarm("operator_disarm")

    # ARM REQUEST
    if args.arm_live:
        su = load_superuser()
        ls = request_arm()

        if ls.state != "ARMED_PENDING":
            print("ARM request rejected (rate-limit/cooldown or safety).")
        else:
            token = generate_token(6)
            write_pending_token(token, ttl_seconds=CONFIRM_TOKEN_TTL_SECONDS)

            ch = input("Send confirm token via Email or SMS? [E/S]: ").strip().upper()
            if ch == "E":
                write_email(su["primary"]["email"], token)
                print(f"Token written to EMAIL outbox for {_mask_email(su['primary']['email'])}")
            else:
                write_sms(su["primary"]["phone_e164"], token)
                print(f"Token written to SMS outbox for {_mask_phone(su['primary']['phone_e164'])}")

            print("ARMED_PENDING created. Confirm requires the 6-char token before TTL expiry.")

    # CONFIRM
    if args.confirm_live:
        from run_preflight import preflight_passed

        if not preflight_passed():
            clear_pending_token()
            force_disarm("preflight_failed")
        elif not validate_token(args.confirm_live):
            clear_pending_token()
            force_disarm("confirm_token_invalid")
        else:
            confirm_arm(preflight_ok=True)
            clear_pending_token()

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
