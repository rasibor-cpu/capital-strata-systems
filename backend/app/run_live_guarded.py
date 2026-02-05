"""
run_live_guarded.py – REA Capital Trading Engine (Phase 1)

LIVE mode:
- Requires a valid session token (6 digits) issued by /auth/verify
- Requires role "superuser"
- Validates via GET /auth/me with Authorization: Bearer <token>

TEST mode:
- Token optional (if provided, we validate and print identity)

Usage:
  # TEST (no token required)
  python -m backend.app.run_live_guarded --mode TEST

  # LIVE (token required)
  python -m backend.app.run_live_guarded --mode LIVE --token 123456

Notes:
- Server must be running: python -m uvicorn backend.app.main:app --reload
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


def ensure_engine_run_id() -> str:
    run_id = os.getenv("ENGINE_RUN_ID", "").strip()
    if not run_id:
        run_id = str(uuid.uuid4())
        os.environ["ENGINE_RUN_ID"] = run_id
    return run_id


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Tuple[int, Dict[str, Any]]:
    headers = headers or {}
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw) if raw else {}
            except Exception:
                return resp.status, {"raw": raw}
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {"raw": raw}
        return int(getattr(e, "code", 0) or 0), body
    except URLError as e:
        return 0, {"error": "network_error", "detail": str(e)}
    except Exception as e:
        return 0, {"error": "unknown_error", "detail": str(e)}


@dataclass(frozen=True)
class AuthDecision:
    allow: bool
    reason: str
    me: Optional[Dict[str, Any]] = None


def validate_session_token(base_url: str, token: str, require_superuser: bool) -> AuthDecision:
    token = (token or "").strip()
    if not token:
        return AuthDecision(False, "Missing session token.")
    if (not token.isdigit()) or len(token) != 6:
        return AuthDecision(False, "Session token must be exactly 6 digits.")

    url = base_url.rstrip("/") + "/auth/me"
    status, data = _http_get_json(url, headers={"Authorization": f"Bearer {token}"})
    if status != 200:
        return AuthDecision(False, f"Token validation failed (status={status}).", me=data)

    roles = data.get("roles") or []
    if require_superuser and "superuser" not in roles:
        return AuthDecision(False, "Token valid but missing required role: superuser.", me=data)

    return AuthDecision(True, "Token valid.", me=data)


def main() -> int:
    parser = argparse.ArgumentParser(description="REA – run_live_guarded")
    parser.add_argument("--mode", choices=["TEST", "LIVE"], default="TEST")
    parser.add_argument("--base-url", default=os.getenv("REA_API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("REA_BEARER_TOKEN", ""))
    args = parser.parse_args()

    run_id = ensure_engine_run_id()
    mode = args.mode.upper().strip()
    base_url = args.base_url.strip()

    print(f"[INFO] ENGINE_RUN_ID={run_id}")
    print(f"[INFO] MODE={mode}")
    print(f"[INFO] API_BASE_URL={base_url}")

    if mode == "LIVE":
        decision = validate_session_token(base_url, args.token, require_superuser=True)
        if not decision.allow:
            print(f"[BLOCK] LIVE auth gate: {decision.reason}")
            if decision.me is not None:
                print(f"[BLOCK] Details: {decision.me}")
            return 1
        print("[ALLOW] LIVE auth gate passed.")
        print(f"[ALLOW] Identity: {decision.me}")
    else:
        # TEST mode
        if (args.token or "").strip():
            decision = validate_session_token(base_url, args.token, require_superuser=False)
            if decision.allow:
                print("[INFO] TEST token valid.")
                print(f"[INFO] Identity: {decision.me}")
            else:
                print(f"[WARN] TEST token invalid: {decision.reason}")
                print(f"[WARN] Details: {decision.me}")
        else:
            print("[INFO] TEST mode: no token provided (ok).")

    print("[INFO] Guard complete. Engine start not invoked by this wrapper (by design).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
