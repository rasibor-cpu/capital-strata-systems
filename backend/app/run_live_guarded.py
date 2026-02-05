"""
run_live_guarded.py – REA Capital Trading Engine (Phase 1/2)

Goals:
- LIVE mode: fail-closed auth gate before any engine action
- Seamless operator flow options:
  A) Provide a 6-digit session token: --token 123456
  B) OR provide username/password and auto-generate session token in one flow:
       --username robert --password 123456 --auto-token
  C) OR omit token in LIVE and it will prompt you to paste it.

Auth model (2-step on API):
- POST /auth/login  -> returns challenge_code (6 digits)
- POST /auth/verify -> returns session token (6 digits)
- GET  /auth/me     -> validates token and returns identity + roles

Phase 2 wiring:
- After LIVE ALLOW, we enter engine_entry.start_engine() in DRY_RUN mode (safe).

Usage:
  # TEST mode (no token required)
  python -m backend.app.run_live_guarded --mode TEST

  # LIVE mode with session token (generated from UI or auto-token)
  python -m backend.app.run_live_guarded --mode LIVE --token 936792

  # LIVE seamless: username+password -> auto-login+verify -> uses issued session token
  python -m backend.app.run_live_guarded --mode LIVE --auto-token --username robert --password 123456

Notes:
- API server must be running:
    python -m uvicorn backend.app.main:app --reload
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# -------------------------------------------------------------------
# basics
# -------------------------------------------------------------------

def ensure_engine_run_id() -> str:
    run_id = os.getenv("ENGINE_RUN_ID", "").strip()
    if not run_id:
        run_id = str(uuid.uuid4())
        os.environ["ENGINE_RUN_ID"] = run_id
    return run_id


def _read_json_safe(raw: str) -> Dict[str, Any]:
    raw = raw or ""
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {"raw": raw}


def _http_json(method: str, url: str, payload: Optional[Dict[str, Any]] = None,
               headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Tuple[int, Dict[str, Any]]:
    headers = headers or {}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=body, headers=headers, method=method.upper())

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, _read_json_safe(raw)

    except HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        return int(getattr(e, "code", 0) or 0), _read_json_safe(raw)

    except URLError as e:
        return 0, {"error": "network_error", "detail": str(e)}

    except Exception as e:
        return 0, {"error": "unknown_error", "detail": str(e)}


def _extract_bearer(token: str) -> str:
    token = (token or "").strip()
    return token


# -------------------------------------------------------------------
# auth decisions
# -------------------------------------------------------------------

@dataclass(frozen=True)
class AuthDecision:
    allow: bool
    reason: str
    token: str = ""
    me: Optional[Dict[str, Any]] = None


def _require_6_digits(value: str, field_name: str) -> Optional[str]:
    v = (value or "").strip()
    if not v:
        return f"Missing {field_name}."
    if (not v.isdigit()) or len(v) != 6:
        return f"{field_name} must be exactly 6 digits."
    return None


def validate_session_token(base_url: str, token: str, require_superuser: bool) -> AuthDecision:
    token = _extract_bearer(token)
    err = _require_6_digits(token, "Session token")
    if err:
        return AuthDecision(False, err, token=token, me=None)

    url = base_url.rstrip("/") + "/auth/me"
    status, data = _http_json("GET", url, headers={"Authorization": f"Bearer {token}"})

    if status != 200:
        return AuthDecision(False, f"Token validation failed (status={status}).", token=token, me=data)

    roles = data.get("roles") or []
    if require_superuser and "superuser" not in roles:
        return AuthDecision(False, "Token valid but missing required role: superuser.", token=token, me=data)

    return AuthDecision(True, "Token valid.", token=token, me=data)


def auto_issue_session_token(base_url: str, username: str, password: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Seamless flow:
      1) POST /auth/login  (username/password) -> challenge_code
      2) POST /auth/verify (challenge_code)    -> session token
    Returns: (token|None, debug_info)
    """
    debug: Dict[str, Any] = {"step1": None, "step2": None}

    # Step 1
    s1_url = base_url.rstrip("/") + "/auth/login"
    s1_status, s1_data = _http_json("POST", s1_url, payload={"username": username, "password": password})
    debug["step1"] = {"status": s1_status, "data": s1_data}

    if s1_status != 200:
        return None, debug

    challenge = (s1_data.get("challenge_code") or "").strip()
    err = _require_6_digits(challenge, "Challenge code")
    if err:
        debug["step1_error"] = err
        return None, debug

    # Step 2
    s2_url = base_url.rstrip("/") + "/auth/verify"
    s2_status, s2_data = _http_json("POST", s2_url, payload={"challenge_code": challenge})
    debug["step2"] = {"status": s2_status, "data": s2_data}

    if s2_status != 200:
        return None, debug

    token = (s2_data.get("token") or "").strip()
    err = _require_6_digits(token, "Session token")
    if err:
        debug["step2_error"] = err
        return None, debug

    return token, debug


# -------------------------------------------------------------------
# main
# -------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="REA – run_live_guarded")
    parser.add_argument("--mode", choices=["TEST", "LIVE"], default="TEST")
    parser.add_argument("--base-url", default=os.getenv("REA_API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("REA_BEARER_TOKEN", ""))
    parser.add_argument("--auto-token", action="store_true", help="Auto issue a session token using username/password.")
    parser.add_argument("--username", default=os.getenv("REA_SUPERUSER", ""))
    parser.add_argument("--password", default=os.getenv("REA_SUPERPASS", ""))
    args = parser.parse_args()

    run_id = ensure_engine_run_id()
    mode = args.mode.upper().strip()
    base_url = args.base_url.strip()

    print(f"[INFO] ENGINE_RUN_ID={run_id}")
    print(f"[INFO] MODE={mode}")
    print(f"[INFO] API_BASE_URL={base_url}")

    token = (args.token or "").strip()

    # --- Seamless token issuance (single-flow) ---
    if mode == "LIVE" and args.auto_token:
        u = (args.username or "").strip()
        p = (args.password or "")
        if not u or not p:
            print("[BLOCK] --auto-token requires --username and --password.")
            return 1

        issued, dbg = auto_issue_session_token(base_url, u, p)
        if not issued:
            print("[BLOCK] Auto token issuance failed.")
            print(f"[BLOCK] Debug: {dbg}")
            return 1

        token = issued
        print(f"[INFO] Auto-issued session token: {token}")

    # --- Prompt for token if LIVE and missing ---
    if mode == "LIVE" and not token:
        token = input("Enter 6-digit session token: ").strip()

    if mode == "LIVE":
        decision = validate_session_token(base_url, token, require_superuser=True)
        if not decision.allow:
            print(f"[BLOCK] LIVE auth gate: {decision.reason}")
            if decision.me is not None:
                print(f"[BLOCK] Details: {decision.me}")
            return 1

        print("[ALLOW] LIVE auth gate passed.")
        print(f"[ALLOW] Identity: {decision.me}")

        # ---- Phase 2: enter engine (DRY-RUN only) ----
        try:
            from backend.app.engine_entry import start_engine
            rc = start_engine(mode="LIVE", identity=decision.me or {}, dry_run=True)
            print(f"[ENGINE] Exit code={rc}")
        except Exception as e:
            print(f"[BLOCK] Engine entry failed: {e}")
            return 2

    else:
        # TEST mode
        if token:
            decision = validate_session_token(base_url, token, require_superuser=False)
            if decision.allow:
                print("[INFO] TEST token valid.")
                print(f"[INFO] Identity: {decision.me}")
            else:
                print(f"[WARN] TEST token invalid: {decision.reason}")
                print(f"[WARN] Details: {decision.me}")
        else:
            print("[INFO] TEST mode: no token provided (ok).")

    print("[INFO] Guard complete. Engine start not invoked beyond DRY_RUN entry (by design).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
