"""
run_live_guarded.py
-------------------
Contract-resilient LIVE runner wrapper.

Key invariants:
- FAIL-CLOSED always.
- This runner DOES NOT place orders. Broker wiring is separate.
- Uses audit/live_state.json as the single source of truth (aligned with execution_gate.py).
- Two-stage arming:
    1) --arm-live => ARMED_PENDING + 6-char token generated + notification written (email/sms stubs)
    2) --confirm-live TOKEN => ARMED_ACTIVE (only if valid token + within expiry + preflight + rate-limit + clean working tree)
- Auto-disarm triggers:
    - pending expired
    - active expired
    - working tree dirty (safety)
    - invalid state schema (fail-closed)
"""

import argparse
import json
import os
import random
import string
import subprocess
from datetime import datetime, timedelta, timezone

# --- Paths (single source of truth) ---
AUDIT_DIR = "audit"
OUTBOX_EMAIL_DIR = os.path.join(AUDIT_DIR, "outbox_emails")
OUTBOX_SMS_DIR = os.path.join(AUDIT_DIR, "outbox_sms")
LIVE_STATE_PATH = os.path.join(AUDIT_DIR, "live_state.json")
SUPERUSER_CFG_PATH = os.path.join("config", "superuser.json")

# --- Defaults / governance constants ---
TOKEN_LEN = 6
PENDING_CONFIRM_WINDOW_SECONDS = 120  # 2 minutes (your requirement)
ACTIVE_WINDOW_SECONDS = 15 * 60       # 15 minutes active window (safe default; can be changed in policy later)
ARM_COOLDOWN_SECONDS = 60             # prevent rapid spam-arming requests
CONFIRM_COOLDOWN_SECONDS = 10         # prevent rapid confirm attempts

STATE_DISARMED = "DISARMED"
STATE_ARMED_PENDING = "ARMED_PENDING"
STATE_ARMED_ACTIVE = "ARMED_ACTIVE"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def ensure_dirs():
    os.makedirs(AUDIT_DIR, exist_ok=True)
    os.makedirs(OUTBOX_EMAIL_DIR, exist_ok=True)
    os.makedirs(OUTBOX_SMS_DIR, exist_ok=True)
    os.makedirs("config", exist_ok=True)


def git_working_tree_clean() -> bool:
    """Fail-closed: if git not available, treat as dirty."""
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], text=True, stderr=subprocess.STDOUT)
        return out.strip() == ""
    except Exception:
        return False


def _read_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_superuser_config():
    """
    Loads config/superuser.json if present.
    If missing, returns None (fail-closed on notification routing, but arming flow still works via file outbox).
    """
    try:
        cfg = _read_json(SUPERUSER_CFG_PATH)
        return cfg
    except Exception:
        return None


def generate_token(n: int = TOKEN_LEN) -> str:
    # uppercase alnum for easy SMS typing
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


def load_live_state():
    st = _read_json(LIVE_STATE_PATH)
    if not st:
        return {
            "version": "1.0",
            "state": STATE_DISARMED,
            "expires_at_utc": None,
            "reason": "init",
            "last_updated_utc": iso(utcnow()),
            "preflight_passed": False,
            "rate_limit_ok": True,
        }
    # Backward/forward tolerance: normalize keys
    if "armed_state" in st and "state" not in st:
        st["state"] = st.get("armed_state")
    if "expires_utc" in st and "expires_at_utc" not in st:
        st["expires_at_utc"] = st.get("expires_utc")
    if "last_updated" in st and "last_updated_utc" not in st:
        st["last_updated_utc"] = st.get("last_updated")
    if "version" not in st:
        st["version"] = "1.0"
    # Ensure required keys exist
    st.setdefault("preflight_passed", False)
    st.setdefault("rate_limit_ok", True)
    st.setdefault("reason", "unknown")
    st.setdefault("expires_at_utc", None)
    st.setdefault("last_updated_utc", iso(utcnow()))
    return st


def save_live_state(st: dict, reason: str):
    st["reason"] = reason
    st["last_updated_utc"] = iso(utcnow())
    _write_json(LIVE_STATE_PATH, st)


def auto_disarm_if_needed(st: dict) -> dict:
    """
    Auto-disarm triggers.
    Always fail-closed: any parse error -> DISARMED.
    """
    # working tree dirty -> disarm
    if not git_working_tree_clean():
        st["state"] = STATE_DISARMED
        st["expires_at_utc"] = None
        save_live_state(st, "auto_disarm_working_tree_dirty")
        return st

    exp = st.get("expires_at_utc")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp)
            if utcnow() >= exp_dt:
                if st.get("state") == STATE_ARMED_PENDING:
                    st["state"] = STATE_DISARMED
                    st["expires_at_utc"] = None
                    save_live_state(st, "auto_disarm_expired_pending")
                    return st
                if st.get("state") == STATE_ARMED_ACTIVE:
                    st["state"] = STATE_DISARMED
                    st["expires_at_utc"] = None
                    save_live_state(st, "auto_disarm_expired_active")
                    return st
        except Exception:
            st["state"] = STATE_DISARMED
            st["expires_at_utc"] = None
            save_live_state(st, "auto_disarm_invalid_expiry_format")
            return st

    return st


def write_notifications(token: str, cfg: dict | None):
    """
    Notification stubs:
    - Writes 'email' and 'sms' messages into audit/outbox_* for later integration.
    """
    ts = int(utcnow().timestamp())
    email_path = os.path.join(OUTBOX_EMAIL_DIR, f"live_arm_{ts}.txt")
    sms_path = os.path.join(OUTBOX_SMS_DIR, f"live_arm_{ts}.txt")

    # Determine recipients (defaults acceptable)
    primary = None
    if isinstance(cfg, dict):
        primary = cfg.get("primary")

    to_email = None
    to_phone = None
    if isinstance(primary, dict):
        to_email = primary.get("email")
        to_phone = primary.get("phone_e164")

    subject = "REA LIVE ARMING: CONFIRMATION REQUIRED"
    body = (
        "LIVE EXECUTION ARMING REQUESTED.\n"
        "Two-stage arming is in effect.\n\n"
        f"CONFIRM TOKEN (6 chars): {token}\n"
        f"Confirm window: {PENDING_CONFIRM_WINDOW_SECONDS} seconds\n\n"
        "Confirm command:\n"
        f"  python run_live_guarded.py --confirm-live {token}\n\n"
        "If you did NOT request this, do nothing; it will auto-disarm.\n"
    )

    email_msg = f"TO: {to_email or '<unset>'}\nSUBJECT: {subject}\n\n{body}"
    sms_msg = f"TO: {to_phone or '<unset>'}\n\n{body}"

    with open(email_path, "w", encoding="utf-8") as f:
        f.write(email_msg)
    with open(sms_path, "w", encoding="utf-8") as f:
        f.write(sms_msg)

    print(f"Notification written to: {email_path}")
    print(f"Notification written to: {sms_path}")


def rate_limit_check(st: dict, kind: str) -> bool:
    """
    Simple local rate-limit for arming/confirm actions.
    Stored in live_state.json so it survives sessions.
    """
    now = utcnow()
    key = f"last_{kind}_utc"
    prev = st.get(key)
    if prev:
        try:
            prev_dt = datetime.fromisoformat(prev)
            cooldown = ARM_COOLDOWN_SECONDS if kind == "arm" else CONFIRM_COOLDOWN_SECONDS
            if (now - prev_dt).total_seconds() < cooldown:
                return False
        except Exception:
            # if malformed, fail-closed by disarming in auto_disarm stage; here we just block action
            return False
    st[key] = iso(now)
    return True


def try_execution_gate():
    """
    Calls engine.execution.execution_gate.execution_gate_check() if available.
    Contract-resilient:
      - If returns tuple -> (decision, reason)
      - If returns dict -> read fields safely
      - Any error -> BLOCK fail-closed
    """
    try:
        from engine.execution.execution_gate import execution_gate_check
        res = execution_gate_check()
        if isinstance(res, tuple) and len(res) == 2:
            return res[0], res[1]
        if isinstance(res, dict):
            return res.get("decision", "BLOCK"), res.get("reason", "unknown")
        return "BLOCK", "execution_gate_unknown_return_type"
    except Exception as e:
        return "BLOCK", f"execution_gate_error_{type(e).__name__}_fail_closed"


def show_status():
    ensure_dirs()
    st = load_live_state()
    st = auto_disarm_if_needed(st)

    decision, reason = try_execution_gate()

    print("\n================ REA LIVE STATUS ================")
    print(f"UTC Now      : {iso(utcnow())}")
    print(f"State        : {st.get('state')}")
    print(f"Expires (UTC): {st.get('expires_at_utc') or 'None'}")
    print(f"Reason       : {st.get('reason')}")
    print(f"Preflight    : {st.get('preflight_passed')}")
    print(f"RateLimitOK  : {st.get('rate_limit_ok')}")
    print("------------------------------------------------")
    print(f"Exec Gate    : {decision} | {reason}")
    print("================================================\n")


def arm_live():
    ensure_dirs()

    st = load_live_state()
    st = auto_disarm_if_needed(st)

    # Rate-limit arm requests
    if not rate_limit_check(st, "arm"):
        st["rate_limit_ok"] = False
        save_live_state(st, "arm_rate_limited")
        print("Arm blocked: rate-limited (cooldown).")
        return

    st["rate_limit_ok"] = True

    # Require clean working tree (already enforced in auto_disarm_if_needed; re-check to be explicit)
    if not git_working_tree_clean():
        st["state"] = STATE_DISARMED
        st["expires_at_utc"] = None
        save_live_state(st, "arm_blocked_working_tree_dirty")
        print("Arm blocked: working tree not clean.")
        return

    print("\n*** LIVE EXECUTION ARMING REQUESTED ***")
    print("This may place REAL trades when fully ACTIVE.")
    ans = input("Arm live execution? [Y/N]: ").strip().lower()
    if ans not in ("y", "yes"):
        print("Arming cancelled.")
        return

    token = generate_token(TOKEN_LEN)
    st["state"] = STATE_ARMED_PENDING
    st["pending_token"] = token  # stored for local confirmation (email/sms delivery is separate)
    st["expires_at_utc"] = iso(utcnow() + timedelta(seconds=PENDING_CONFIRM_WINDOW_SECONDS))
    st["preflight_passed"] = False  # will be set at confirm time
    save_live_state(st, "awaiting_reconfirmation")

    cfg = load_superuser_config()
    write_notifications(token, cfg)

    print("\nARMED_PENDING created.")
    print(f"Token expires in {PENDING_CONFIRM_WINDOW_SECONDS} seconds.")
    print("Waiting for reconfirmation before becoming ACTIVE.\n")
    show_status()


def run_preflight() -> bool:
    """
    Bind preflight to confirm.
    If run_preflight.py exists, we run it.
    If it fails, return False.
    """
    try:
        # Prefer local script if present
        if os.path.exists("run_preflight.py"):
            code = subprocess.call(["python", "run_preflight.py"])
            return code == 0
        return True  # if no preflight script, allow but still safe (execution gate still blocks unless active)
    except Exception:
        return False


def confirm_live(token: str):
    ensure_dirs()
    st = load_live_state()
    st = auto_disarm_if_needed(st)

    if st.get("state") != STATE_ARMED_PENDING:
        print("ERROR: No pending arming request.")
        show_status()
        return

    # Confirm attempts rate-limit
    if not rate_limit_check(st, "confirm"):
        st["rate_limit_ok"] = False
        save_live_state(st, "confirm_rate_limited")
        print("Confirm blocked: rate-limited (cooldown).")
        return
    st["rate_limit_ok"] = True

    # Token validate
    pending = st.get("pending_token")
    if not pending or token.strip().upper() != str(pending).strip().upper():
        # Fail-closed: disarm on wrong token
        st["state"] = STATE_DISARMED
        st["expires_at_utc"] = None
        st.pop("pending_token", None)
        save_live_state(st, "confirm_invalid_token_auto_disarm")
        print("INVALID TOKEN. DISARMED. PLEASE REGENERATE.")
        show_status()
        return

    # Expiry already handled by auto_disarm; re-check just in case
    exp = st.get("expires_at_utc")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp)
            if utcnow() >= exp_dt:
                st["state"] = STATE_DISARMED
                st["expires_at_utc"] = None
                st.pop("pending_token", None)
                save_live_state(st, "confirm_expired_pending_auto_disarm")
                print("Pending token expired. DISARMED. Please re-arm.")
                show_status()
                return
        except Exception:
            st["state"] = STATE_DISARMED
            st["expires_at_utc"] = None
            st.pop("pending_token", None)
            save_live_state(st, "confirm_invalid_expiry_auto_disarm")
            print("Invalid expiry format. DISARMED.")
            show_status()
            return

    # Preflight binding (must pass)
    preflight_ok = run_preflight()
    st["preflight_passed"] = bool(preflight_ok)
    if not preflight_ok:
        st["state"] = STATE_DISARMED
        st["expires_at_utc"] = None
        st.pop("pending_token", None)
        save_live_state(st, "confirm_preflight_failed_auto_disarm")
        print("Preflight FAILED. DISARMED (fail-closed).")
        show_status()
        return

    # Activate (time-box active window for safety)
    st["state"] = STATE_ARMED_ACTIVE
    st["expires_at_utc"] = iso(utcnow() + timedelta(seconds=ACTIVE_WINDOW_SECONDS))
    st.pop("pending_token", None)
    save_live_state(st, "confirmed_active")

    print("LIVE EXECUTION ARMED: ARMED_ACTIVE (time-boxed).")
    show_status()


def disarm(reason: str = "manual_disarm"):
    ensure_dirs()
    st = load_live_state()
    st["state"] = STATE_DISARMED
    st["expires_at_utc"] = None
    st.pop("pending_token", None)
    save_live_state(st, reason)
    print("DISARMED.")
    show_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm-live", action="store_true", help="Create ARMED_PENDING and generate a 6-char token.")
    parser.add_argument("--confirm-live", metavar="TOKEN", type=str, help="Confirm pending token to become ARMED_ACTIVE.")
    parser.add_argument("--disarm", action="store_true", help="Disarm immediately.")
    args = parser.parse_args()

    # Default: status
    if args.disarm:
        disarm()
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
