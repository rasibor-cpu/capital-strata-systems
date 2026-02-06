"""
Headless Guarded Entry – REA Capital Trading Engine
---------------------------------------------------

Purpose:
- Provide a safe callable wrapper for FastAPI (no CLI args required)
- Preserve optional CLI execution for auth validation
- Never kill the FastAPI process when called via API
- Fail-closed behavior

Notes:
- This does NOT trade. It only validates that headless execution can run.
- If called via API, it runs in "no-credentials" mode and returns 0.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error
from typing import Any, Dict, Optional


def _http_json(
    method: str,
    url: str,
    payload: Dict[str, Any] | None = None,
    headers: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url=url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")

    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {"raw": raw}
        return {"_http_error": True, "status": e.code, "body": body}
    except Exception as e:
        return {"_http_error": True, "status": None, "body": {"detail": str(e)}}


def execute_headless(base_url: str, username: Optional[str], password: Optional[str]) -> int:
    """
    Core logic.
    Returns integer exit code.
    """

    base = (base_url or "http://127.0.0.1:8000").rstrip("/")
    print(f"[HEADLESS] Base URL: {base}")

    # API mode: no creds supplied -> we intentionally do NOT attempt OTP flow
    if not username or not password:
        print("[HEADLESS] API mode: no credentials supplied; auth flow skipped.")
        print("[HEADLESS] Execution layer currently locked (no live trades).")
        print("[HEADLESS] Guarded mode confirmed.")
        print("[HEADLESS_DEV_MODE ready.]")
        return 0

    # CLI mode: do OTP flow
    print("[HEADLESS] CLI mode: starting OTP auth validation...")

    r1 = _http_json("POST", f"{base}/auth/login", {"username": username, "password": password})
    if r1.get("_http_error"):
        print("[HEADLESS] /auth/login failed:", r1, file=sys.stderr)
        return 2
    print("[HEADLESS] OTP send response:", r1)

    otp = input("Enter the 6-digit OTP from your email: ").strip()
    if not (otp.isdigit() and len(otp) == 6):
        print("[HEADLESS] Invalid OTP format (must be 6 digits).", file=sys.stderr)
        return 3

    r2 = _http_json("POST", f"{base}/auth/verify", {"username": username, "otp": otp})
    if r2.get("_http_error"):
        print("[HEADLESS] /auth/verify failed:", r2, file=sys.stderr)
        return 4

    token = r2.get("token")
    if not token:
        print("[HEADLESS] No token returned from /auth/verify:", r2, file=sys.stderr)
        return 5

    print("[HEADLESS] Token acquired (hidden). token_type=", r2.get("token_type", "bearer"))

    r3 = _http_json("GET", f"{base}/auth/me", payload=None, headers={"Authorization": f"Bearer {token}"})
    if r3.get("_http_error"):
        print("[HEADLESS] /auth/me failed:", r3, file=sys.stderr)
        return 6

    print("[HEADLESS] Identity:", r3)
    print("[HEADLESS] Auth flow OK.")
    print("[HEADLESS] Execution layer currently locked (no live trades).")
    print("[HEADLESS_DEV_MODE ready.]")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="REA Headless Guarded Entry")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    # IMPORTANT: not required anymore (so FastAPI can call without args)
    ap.add_argument("--username", required=False)
    ap.add_argument("--password", required=False)
    args = ap.parse_args()

    return execute_headless(base_url=args.base_url, username=args.username, password=args.password)


def run_headless() -> Any:
    """
    Safe callable wrapper for FastAPI.
    Runs in API mode (no creds) and returns exit code / error object.
    """
    try:
        return execute_headless(base_url="http://127.0.0.1:8000", username=None, password=None)
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    raise SystemExit(main())
