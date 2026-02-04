#!/usr/bin/env python3
"""
REA Live Guarded Runner (contract-resilient, fail-closed)

Problem solved:
- Do NOT import specific function names that may not exist (e.g., check_rate_limit).
- Import modules and use getattr fallbacks.
- Persist live state directly to audit/live_state.json (writer-independent).

Security invariants:
- Default DISARMED.
- ARMED_PENDING remains BLOCK until confirm succeeds.
- Confirm window: 120s.
- Token length: 6 chars.
- If any dependency is missing/unknown -> fail-closed (BLOCK / disallow arming).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
import importlib

LIVE_STATE_PATH = os.path.join("audit", "live_state.json")
CONFIRM_WINDOW_SECONDS = 120  # 2 minutes


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _read_state() -> dict:
    base = {
        "armed_state": "DISARMED",
        "token": None,
        "expires_at_utc": None,
        "reason": "default_disarmed",
        "last_updated_utc": utcnow().isoformat(),
    }

    if not os.path.exists(LIVE_STATE_PATH):
        return base

    try:
        with open(LIVE_STATE_PATH, "r", encoding="utf-8") as f:
            d = json.load(f) or {}
    except Exception:
        return base | {"reason": "corrupt_state_fail_closed"}

    # backward compat: state vs armed_state
    armed_state = d.get("armed_state") or d.get("state") or base["armed_state"]
    expires = d.get("expires_at_utc") or d.get("expires_utc") or None

    out = dict(d)
    out["armed_state"] = armed_state
    out["expires_at_utc"] = expires
    out.setdefault("token", None)
    out.setdefault("reason", "loaded")
    out.setdefault("last_updated_utc", utcnow().isoformat())

    if out["armed_state"] not in {"DISARMED", "ARMED_PENDING", "ARMED_ACTIVE"}:
        return base | {"reason": "unknown_state_fail_closed"}

    return out


def _write_state(d: dict) -> None:
    _ensure_parent_dir(LIVE_STATE_PATH)
    d["last_updated_utc"] = utcnow().isoformat()
    with open(LIVE_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, sort_keys=True)


def disarm(reason: str) -> None:
    d = _read_state()
    d["armed_state"] = "DISARMED"
    d["token"] = None
    d["expires_at_utc"] = None
    d["reason"] = reason
    _write_state(d)


def auto_disarm_if_needed() -> None:
    d = _read_state()
    if d.get("armed_state") == "ARMED_PENDING" and d.get("expires_at_utc"):
        try:
            exp = datetime.fromisoformat(d["expires_at_utc"])
            if utcnow() > exp:
                disarm("auto_disarm_expired_pending")
        except Exception:
            disarm("auto_disarm_bad_expiry")


def _generate_token() -> str:
    import secrets
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _write_outbox_notification(token: str, expires: datetime) -> None:
    ts = int(time.time())
    path = os.path.join("audit", "outbox_emails", f"live_arm_{ts}.txt")
    _ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write("REA LIVE EXECUTION CONFIRMATION\n\n")
        f.write(f"TOKEN: {token}\n")
        f.write(f"EXPIRES (UTC): {expires.isoformat()}\n")
        f.write("\nConfirm via:\n")
        f.write("python run_live_guarded.py --confirm-live <TOKEN>\n")


# -----------------------------
# CONTRACT-RESILIENT LOADERS
# -----------------------------

def _try_import(module_name: str):
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None


def _safe_print_banner():
    mod = _try_import("engine.runtime.live_banner")
    if mod and hasattr(mod, "print_live_banner"):
        try:
            mod.print_live_banner()
            return
        except Exception:
            pass
    # fallback banner
    d = _read_state()
    print("\n================= REA LIVE STATUS =================")
    print(f"UTC Now       : {utcnow().isoformat()}")
    print(f"State         : {d.get('armed_state')}")
    print(f"Expires (UTC) : {d.get('expires_at_utc')}")
    print(f"Reason        : {d.get('reason')}")
    print("==================================================\n")


def _load_superuser_config() -> dict:
    """
    Prefer config.superuser.load_superuser() if present.
    Otherwise read config/superuser.json directly (fail-closed if missing/invalid).
    """
    # Preferred loader
    mod = _try_import("config.superuser")
    if mod and hasattr(mod, "load_superuser"):
        su = mod.load_superuser()
        if su:
            return su

    # Fallback file read
    path = os.path.join("config", "superuser.json")
    if not os.path.exists(path):
        raise RuntimeError("Superuser config missing: config/superuser.json")

    try:
        with open(path, "r", encoding="utf-8") as f:
            su = json.load(f)
    except Exception as e:
        raise RuntimeError(f"Superuser config unreadable: {e}")

    # Minimal validation
    primary = (su or {}).get("primary") or {}
    email = primary.get("email")
    phone = primary.get("phone_e164")
    if not email or not phone:
        raise RuntimeError("Superuser config invalid: primary.email and primary.phone_e164 required")
    return su


def _rate_limit_ok() -> bool:
    """
    Arming rate-limit. We do NOT assume any specific function name.
    We call the first one found in this order:
      - check_rate_limit()
      - check_arming_rate_limit()
      - arming_rate_limit_ok()
    If none exists -> FAIL-CLOSED (return False).
    """
    mod = _try_import("engine.execution.arming_rate_limit")
    if not mod:
        return False

    for fn_name in ("check_rate_limit", "check_arming_rate_limit", "arming_rate_limit_ok"):
        fn = getattr(mod, fn_name, None)
        if callable(fn):
            try:
                return bool(fn())
            except Exception:
                return False

    return False  # fail-closed


def _run_preflight_or_fail() -> None:
    """
    Preflight bound to confirm. If module missing -> fail-closed.
    """
    mod = _try_import("engine.execution.preflight")
    if not mod or not hasattr(mod, "run_preflight"):
        raise RuntimeError("Preflight module not available (fail-closed).")
    mod.run_preflight()


def _execution_gate_decision() -> dict:
    """
    If execution gate module missing -> fail-closed BLOCK.
    """
    mod = _try_import("engine.execution.execution_gate")
    if not mod:
        return {"decision": "BLOCK", "reason": "execution_gate_missing_fail_closed"}
    fn = getattr(mod, "execution_gate_check", None)
    if not callable(fn):
        return {"decision": "BLOCK", "reason": "execution_gate_fn_missing_fail_closed"}
    try:
        return fn()
    except Exception:
        return {"decision": "BLOCK", "reason": "execution_gate_error_fail_closed"}


# -----------------------------
# COMMANDS
# -----------------------------

def arm_live() -> None:
    # require superuser configured
    try:
        _ = _load_superuser_config()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if not _rate_limit_ok():
        print("RATE LIMIT (or missing limiter): Arming blocked (fail-closed).")
        sys.exit(1)

    print("\n*** LIVE EXECUTION ARMING REQUESTED ***")
    print("This may place REAL trades when fully ACTIVE.")
    ans = input("Arm live execution? [Y/N]: ").strip().lower()
    if ans != "y":
        print("Aborted. Live execution remains DISABLED.")
        return

    token = _generate_token()
    expires = utcnow() + timedelta(seconds=CONFIRM_WINDOW_SECONDS)

    d = _read_state()
    d["armed_state"] = "ARMED_PENDING"
    d["token"] = token
    d["expires_at_utc"] = expires.isoformat()
    d["reason"] = "awaiting_reconfirmation"
    _write_state(d)

    _write_outbox_notification(token, expires)

    print("\nARMED_PENDING created.")
    print("Notification written to audit outbox.")
    print("Waiting for reconfirmation before becoming ACTIVE.")
    print(f"Token expires in {CONFIRM_WINDOW_SECONDS} seconds.")
    print("\nSAFE: Execution remains BLOCKED.")


def confirm_live(token: str) -> None:
    auto_disarm_if_needed()
    d = _read_state()

    if d.get("armed_state") != "ARMED_PENDING":
        print("ERROR: No pending arming request.")
        disarm("confirm_no_pending")
        sys.exit(1)

    exp_s = d.get("expires_at_utc")
    if not exp_s:
        print("ERROR: Missing expiry. Fail-closed.")
        disarm("confirm_missing_expiry")
        sys.exit(1)

    try:
        exp = datetime.fromisoformat(exp_s)
    except Exception:
        print("ERROR: Bad expiry. Fail-closed.")
        disarm("confirm_bad_expiry")
        sys.exit(1)

    if utcnow() > exp:
        print("ERROR: Token expired.")
        disarm("confirm_expired")
        sys.exit(1)

    if token.strip() != str(d.get("token") or "").strip():
        print("INVALID TOKEN. PLEASE REGENERATE.")
        disarm("confirm_invalid_token")
        sys.exit(1)

    # Preflight is mandatory on confirm
    try:
        _run_preflight_or_fail()
    except Exception as e:
        print(f"ERROR: Preflight failed: {e}")
        disarm("preflight_failed")
        sys.exit(1)

    d["armed_state"] = "ARMED_ACTIVE"
    d["token"] = None
    d["expires_at_utc"] = None
    d["reason"] = "confirmed"
    _write_state(d)

    print("\nLIVE EXECUTION ARMED (ACTIVE).")
    print("NOTE: Broker wiring still required to place orders.")


def show_status() -> None:
    auto_disarm_if_needed()
    d = _read_state()

    print("\n================= REA LIVE STATUS =================")
    print(f"UTC Now       : {utcnow().isoformat()}")
    print(f"State         : {d.get('armed_state')}")
    print(f"Expires (UTC) : {d.get('expires_at_utc')}")
    print(f"Reason        : {d.get('reason')}")
    print("==================================================\n")

    decision = _execution_gate_decision()
    print(f"Exec Gate     : {decision.get('decision')} | {decision.get('reason')}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm-live", action="store_true")
    parser.add_argument("--confirm-live", type=str)
    parser.add_argument("--disarm", action="store_true")
    args = parser.parse_args()

    _safe_print_banner()

    if args.disarm:
        disarm("manual")
        print("Live execution DISARMED.")
        return

    if args.arm_live:
        arm_live()
        return

    if args.confirm_live:
        confirm_live(args.confirm_live)
        return

    show_status()


if __name__ == "__main__":
    main()
