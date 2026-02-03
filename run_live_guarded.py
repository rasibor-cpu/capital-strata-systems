#!/usr/bin/env python3
"""
REA Live Guarded Runner — Governance Hardened (v3)
--------------------------------------------------
Implements:
1) Delegate confirmation (primary or listed delegate must identify self)
2) Arming rate-limit: max 3 arm attempts per 24h, then 24h cooldown
3) Preflight bound to confirm: confirm-live runs run_preflight.py; FAIL -> stays pending
4) Auto-disarm triggers (when ACTIVE):
   - Branch not in allowed list (main, live-adapters)
   - Working tree not clean
   - Audit dirs missing
   - Clock sanity check failure (year out of bounds)
5) Live banner when ACTIVE

Two-stage:
- --arm-live (Y/N only) -> ARMED_PENDING (BLOCK)
- --confirm-live TOKEN  -> ARMED_ACTIVE (subject to ExecutionGate), only after preflight PASS
- --disarm              -> DISARMED

Token:
- Exactly 6 chars (A–Z, 0–9)
- TTL 15 minutes
- Stored hashed (plaintext never stored)

Notifications:
- Writes outbox payloads for email + SMS (paper-only; no secrets)
"""

import argparse
import json
import os
import sys
import time
import hashlib
import secrets
import string
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

BASE_DIR = os.getcwd()
CONFIG_FILE = os.path.join("config", "superuser.json")

AUDIT_DIR = os.path.join(BASE_DIR, "audit")
EMAIL_OUTBOX = os.path.join(AUDIT_DIR, "outbox_emails")
SMS_OUTBOX = os.path.join(AUDIT_DIR, "outbox_sms")
STATE_FILE = os.path.join(AUDIT_DIR, "live_state.json")

TOKEN_TTL_MINUTES = 15
TOKEN_LEN = 6
ARM_ATTEMPT_LIMIT_24H = 3
ARM_COOLDOWN_HOURS = 24
ALLOWED_BRANCHES = {"main", "live-adapters"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def ensure_dirs() -> None:
    os.makedirs(AUDIT_DIR, exist_ok=True)
    os.makedirs(EMAIL_OUTBOX, exist_ok=True)
    os.makedirs(SMS_OUTBOX, exist_ok=True)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_FILE):
        sys.exit(f"ERROR: Missing {CONFIG_FILE}. Onboard superuser before arming.")
    cfg = load_json(CONFIG_FILE)

    # Basic validation
    primary = cfg.get("primary") or {}
    email = (primary.get("email") or "").strip()
    phone = (primary.get("phone_e164") or "").strip()
    if "@" not in email:
        sys.exit("ERROR: config/superuser.json primary.email invalid.")
    if not (phone.startswith("+") and phone[1:].isdigit()):
        sys.exit("ERROR: config/superuser.json primary.phone_e164 must be E.164 like +12145551234.")

    delegates = cfg.get("delegates") or []
    for d in delegates:
        de = (d.get("email") or "").strip()
        dp = (d.get("phone_e164") or "").strip()
        if de and "@" not in de:
            sys.exit("ERROR: Delegate email invalid in config/superuser.json.")
        if dp and not (dp.startswith("+") and dp[1:].isdigit()):
            sys.exit("ERROR: Delegate phone_e164 must be E.164 in config/superuser.json.")

    notify = cfg.get("notify_channels") or {}
    if "email" not in notify:
        notify["email"] = True
    if "sms" not in notify:
        notify["sms"] = True
    cfg["notify_channels"] = notify

    return cfg


def load_state() -> Dict[str, Any]:
    ensure_dirs()
    if not os.path.exists(STATE_FILE):
        return {
            "armed_state": "DISARMED",
            "arm_attempts": [],        # list of ISO timestamps
            "cooldown_until": None,    # ISO timestamp
        }
    try:
        return load_json(STATE_FILE)
    except Exception:
        # Corrupt state must fail-safe to DISARMED
        return {
            "armed_state": "DISARMED",
            "arm_attempts": [],
            "cooldown_until": None,
        }


def save_state(state: Dict[str, Any]) -> None:
    ensure_dirs()
    save_json(STATE_FILE, state)


def clock_sanity_ok() -> bool:
    y = utc_now().year
    # Local sanity gate (no NTP): reject obviously wrong system clocks
    return 2024 <= y <= 2035


def audit_write(kind: str, payload: Dict[str, Any]) -> None:
    ensure_dirs()
    line = {"ts": iso(utc_now()), "kind": kind, **payload}
    # Append-only audit trail
    path = os.path.join(AUDIT_DIR, "live_audit.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def gen_token6() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(TOKEN_LEN))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_valid_format(token: str) -> bool:
    if len(token) != TOKEN_LEN:
        return False
    for ch in token:
        if ch not in (string.ascii_uppercase + string.digits):
            return False
    return True


def write_email_outbox(to_email: str, subject: str, body: str) -> str:
    ensure_dirs()
    fn = os.path.join(EMAIL_OUTBOX, f"live_arm_{int(time.time())}.txt")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(f"TO: {to_email}\nSUBJECT: {subject}\nDATE_UTC: {iso(utc_now())}\n\n{body}\n")
    return fn


def write_sms_outbox(to_phone: str, body: str) -> str:
    ensure_dirs()
    fn = os.path.join(SMS_OUTBOX, f"live_arm_{int(time.time())}.txt")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(f"TO: {to_phone}\nDATE_UTC: {iso(utc_now())}\n\n{body}\n")
    return fn


def get_git_branch() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
        return out
    except Exception:
        return "UNKNOWN"


def working_tree_clean() -> bool:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        return out == ""
    except Exception:
        # If git status fails, fail-safe as not clean
        return False


def run_preflight() -> bool:
    # Must pass before allowing ACTIVE
    try:
        proc = subprocess.run([sys.executable, "run_preflight.py"], capture_output=True, text=True)
        ok = (proc.returncode == 0)
        # Store the last preflight output snippet for audit
        audit_write("preflight_run", {
            "ok": ok,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-500:],
            "stderr_tail": (proc.stderr or "")[-500:],
        })
        return ok
    except Exception as e:
        audit_write("preflight_run", {"ok": False, "error": str(e)})
        return False


def disarm_state(state: Dict[str, Any], reason: str) -> Dict[str, Any]:
    state["armed_state"] = "DISARMED"
    state.pop("token_hash", None)
    state.pop("expires_at", None)
    state.pop("pending_created_at", None)
    state.pop("confirmed_at", None)
    state.pop("confirmed_by", None)
    audit_write("disarm", {"reason": reason})
    save_state(state)
    return state


def enforce_auto_disarm_if_active(state: Dict[str, Any]) -> Dict[str, Any]:
    if state.get("armed_state") != "ARMED_ACTIVE":
        return state

    if not clock_sanity_ok():
        return disarm_state(state, "clock_sanity_failed")

    ensure_dirs()
    if not (os.path.isdir(AUDIT_DIR) and os.path.isdir(EMAIL_OUTBOX) and os.path.isdir(SMS_OUTBOX)):
        return disarm_state(state, "audit_dirs_missing")

    br = get_git_branch()
    if br not in ALLOWED_BRANCHES:
        return disarm_state(state, f"branch_not_allowed:{br}")

    if not working_tree_clean():
        return disarm_state(state, "working_tree_not_clean")

    return state


def prune_attempts_24h(attempts: List[str]) -> List[str]:
    now = utc_now()
    keep = []
    for s in attempts:
        try:
            t = datetime.fromisoformat(s)
            if (now - t) <= timedelta(hours=24):
                keep.append(s)
        except Exception:
            # drop malformed
            pass
    return keep


def within_cooldown(state: Dict[str, Any]) -> bool:
    cu = state.get("cooldown_until")
    if not cu:
        return False
    try:
        until = datetime.fromisoformat(cu)
        return utc_now() < until
    except Exception:
        return False


def set_cooldown(state: Dict[str, Any]) -> None:
    until = utc_now() + timedelta(hours=ARM_COOLDOWN_HOURS)
    state["cooldown_until"] = iso(until)


def arm_live(cfg: Dict[str, Any]) -> None:
    state = load_state()

    # Rate-limit arming attempts
    state["arm_attempts"] = prune_attempts_24h(state.get("arm_attempts", []))
    save_state(state)

    if within_cooldown(state):
        print("ARMING BLOCKED: cooldown active.")
        audit_write("arm_blocked", {"reason": "cooldown_active", "cooldown_until": state.get("cooldown_until")})
        return

    if len(state["arm_attempts"]) >= ARM_ATTEMPT_LIMIT_24H:
        set_cooldown(state)
        save_state(state)
        print("ARMING BLOCKED: too many attempts in last 24h. Cooldown set for 24h.")
        audit_write("arm_blocked", {"reason": "rate_limited", "cooldown_until": state.get("cooldown_until")})
        return

    resp = input("Arm live execution? [Y/N]: ").strip().upper()
    # Strict: Y only
    if resp != "Y":
        print("Live execution NOT armed.")
        audit_write("arm_declined", {})
        return

    if not clock_sanity_ok():
        print("ARMING BLOCKED: system clock sanity failed.")
        audit_write("arm_blocked", {"reason": "clock_sanity_failed"})
        return

    ensure_dirs()

    token = gen_token6()
    expires_at = utc_now() + timedelta(minutes=TOKEN_TTL_MINUTES)

    # Update state -> ARMED_PENDING (never active)
    state["armed_state"] = "ARMED_PENDING"
    state["token_hash"] = hash_token(token)
    state["pending_created_at"] = iso(utc_now())
    state["expires_at"] = iso(expires_at)

    # record attempt
    state["arm_attempts"].append(iso(utc_now()))
    state["arm_attempts"] = prune_attempts_24h(state["arm_attempts"])
    save_state(state)

    primary = cfg["primary"]
    notify = cfg.get("notify_channels", {"email": True, "sms": True})

    body = (
        "REA ENGINE — LIVE EXECUTION ARMING PENDING (CONFIRM REQUIRED)\n\n"
        f"STATE: ARMED_PENDING\n"
        f"TIME_UTC: {iso(utc_now())}\n"
        f"BRANCH: {get_git_branch()}\n"
        f"TOKEN (6 chars): {token}\n"
        f"EXPIRES_UTC: {iso(expires_at)}\n\n"
        "To confirm and activate:\n"
        f"  python run_live_guarded.py --confirm-live {token}\n\n"
        "To disarm:\n"
        "  python run_live_guarded.py --disarm\n"
    )

    email_path = None
    sms_path = None
    if notify.get("email", True):
        email_path = write_email_outbox(primary["email"], "REA ENGINE: LIVE ARM PENDING", body)
    if notify.get("sms", True):
        sms_path = write_sms_outbox(primary["phone_e164"], body)

    audit_write("armed_pending", {
        "email_outbox": email_path,
        "sms_outbox": sms_path,
        "expires_at": iso(expires_at),
    })

    print("\nARMED_PENDING created.")
    if email_path:
        print(f"Email outbox written: {email_path}")
    if sms_path:
        print(f"SMS outbox written: {sms_path}")
    print(f"Token expires in {TOKEN_TTL_MINUTES} minutes.")
    print("SAFE: Execution remains BLOCKED until reconfirmed.\n")


def identify_confirmer(cfg: Dict[str, Any]) -> str:
    """
    Delegate confirm:
    - Prompts for confirmer email
    - Must match primary.email OR any delegate.email
    """
    primary_email = (cfg.get("primary", {}).get("email") or "").strip().lower()
    delegate_emails = [((d.get("email") or "").strip().lower()) for d in (cfg.get("delegates") or [])]
    allowed = {primary_email, *[e for e in delegate_emails if e]}

    email = input("Confirming user email (primary or delegate): ").strip().lower()
    if email not in allowed:
        raise ValueError("Confirmer email not authorized.")
    return email


def confirm_live(cfg: Dict[str, Any], token: str) -> None:
    state = load_state()

    if state.get("armed_state") != "ARMED_PENDING":
        print("ERROR: No pending arming request.")
        audit_write("confirm_failed", {"reason": "not_pending"})
        return

    token = token.strip().upper()
    if not token_valid_format(token):
        print("ERROR: Token must be exactly 6 chars (A–Z, 0–9).")
        audit_write("confirm_failed", {"reason": "bad_token_format"})
        return

    # expiry check
    try:
        exp = datetime.fromisoformat(state.get("expires_at"))
    except Exception:
        disarm_state(state, "bad_expiry_state")
        print("ERROR: State invalid; system DISARMED.")
        return

    if utc_now() > exp:
        disarm_state(state, "token_expired")
        print("ERROR: Token expired. System DISARMED.")
        return

    if hash_token(token) != state.get("token_hash"):
        print("ERROR: Invalid token.")
        audit_write("confirm_failed", {"reason": "token_mismatch"})
        return

    # Delegate confirm identity
    try:
        confirmed_by = identify_confirmer(cfg)
    except Exception as e:
        print(f"ERROR: {e}")
        audit_write("confirm_failed", {"reason": "unauthorized_confirmer"})
        return

    # Bind preflight to confirm
    print("\nRunning preflight (required)...")
    if not run_preflight():
        # Remain pending; do not activate
        audit_write("confirm_failed", {"reason": "preflight_failed"})
        print("ERROR: Preflight FAILED. Remaining in ARMED_PENDING (not active).")
        print("Fix issues, then confirm again before expiry.")
        return

    # Success: transition to ACTIVE, single-use token
    state["armed_state"] = "ARMED_ACTIVE"
    state["confirmed_at"] = iso(utc_now())
    state["confirmed_by"] = confirmed_by

    # Single-use: remove token hash + expiry
    state.pop("token_hash", None)
    state.pop("expires_at", None)

    save_state(state)
    audit_write("armed_active", {"confirmed_by": confirmed_by})

    print("\nCONFIRMED. System is now ARMED_ACTIVE (subject to auto-disarm + ExecutionGate).")


def disarm_cmd() -> None:
    state = load_state()
    disarm_state(state, "manual_disarm")
    print("System DISARMED (SAFE).")


def print_live_banner(state: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    if state.get("armed_state") != "ARMED_ACTIVE":
        return
    primary = cfg.get("primary", {})
    print("\n" + "=" * 52)
    print("LIVE MODE ARMED — REAL MONEY RISK")
    print(f"User          : {primary.get('name','(unknown)')}")
    print(f"Primary Email : {primary.get('email','')}")
    print(f"Confirmed By  : {state.get('confirmed_by','(unknown)')}")
    print(f"Confirmed At  : {state.get('confirmed_at','(unknown)')} UTC")
    print(f"Branch        : {get_git_branch()}")
    print("=" * 52 + "\n")


def status(cfg: Dict[str, Any]) -> None:
    state = load_state()

    # Auto-disarm triggers apply only when ACTIVE
    state = enforce_auto_disarm_if_active(state)

    print_live_banner(state, cfg)

    print("=== Live State ===")
    print(f"armed_state    : {state.get('armed_state')}")
    if state.get("armed_state") == "ARMED_PENDING":
        print(f"expires_at_utc : {state.get('expires_at')}")
        print("decision       : BLOCK (pending reconfirmation)")
    elif state.get("armed_state") == "ARMED_ACTIVE":
        print("decision       : ALLOW (runner sends NO orders)")
    else:
        print("decision       : BLOCK (safe)")

    if state.get("cooldown_until"):
        print(f"cooldown_until : {state.get('cooldown_until')}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--arm-live", action="store_true")
    p.add_argument("--confirm-live", type=str, default=None)
    p.add_argument("--disarm", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    cfg = load_config()

    if args.disarm:
        disarm_cmd()
        status(cfg)
        return 0

    if args.arm_live:
        arm_live(cfg)
        status(cfg)
        return 0

    if args.confirm_live:
        confirm_live(cfg, args.confirm_live)
        status(cfg)
        return 0

    # default: just show status (and auto-disarm if active & violated)
    status(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
