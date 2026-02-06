"""
Headless Auth Runner – REA Capital Trading Engine

Purpose:
- Validate auth/OTP flow without the browser UI.
- Sends OTP via /auth/login
- Prompts user for the OTP
- Verifies OTP via /auth/verify
- Confirms identity via /auth/me

Usage (CMD):
  python -m backend.app.headless_auth --base-url http://127.0.0.1:8000 --username robert --password 123456

Notes:
- This runner does NOT trade. It only validates authentication.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from typing import Any, Dict


def _http_json(method: str, url: str, payload: Dict[str, Any] | None = None, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    args = ap.parse_args()

    base = args.base_url.rstrip("/")

    print(f"[HEADLESS] Base URL: {base}")

    # 1) Send OTP
    r1 = _http_json("POST", f"{base}/auth/login", {"username": args.username, "password": args.password})
    if r1.get("_http_error"):
        print("[HEADLESS] /auth/login failed:", r1, file=sys.stderr)
        return 2
    print("[HEADLESS] OTP send response:", r1)

    # 2) Prompt for OTP
    otp = input("Enter the 6-digit OTP from your email: ").strip()
    if not (otp.isdigit() and len(otp) == 6):
        print("[HEADLESS] Invalid OTP format (must be 6 digits).", file=sys.stderr)
        return 3

    # 3) Verify OTP -> token
    r2 = _http_json("POST", f"{base}/auth/verify", {"username": args.username, "otp": otp})
    if r2.get("_http_error"):
        print("[HEADLESS] /auth/verify failed:", r2, file=sys.stderr)
        return 4

    token = r2.get("token")
    if not token:
        print("[HEADLESS] No token returned from /auth/verify:", r2, file=sys.stderr)
        return 5

    print("[HEADLESS] Token acquired (hidden). token_type=", r2.get("token_type", "bearer"))

    # 4) Confirm identity
    r3 = _http_json("GET", f"{base}/auth/me", payload=None, headers={"Authorization": f"Bearer {token}"})
    if r3.get("_http_error"):
        print("[HEADLESS] /auth/me failed:", r3, file=sys.stderr)
        return 6

    print("[HEADLESS] Identity:", r3)
    print("[HEADLESS] Auth flow OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
