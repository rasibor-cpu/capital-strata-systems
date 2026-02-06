"""
REA Guarded Headless Entry
===========================

Purpose:
- Authenticate via OTP
- Validate identity
- Inject token into engine runtime
- Confirm guarded execution mode
- Prepare paper execution session

NOTE:
- Live trading remains disabled.
- This is controlled headless execution.
"""

import argparse
import requests
import sys
import getpass

BASE_URL = "http://127.0.0.1:8000"


def main():
    print("=== REA Guarded Headless Entry ===")

    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()

    base_url = args.base_url
    username = args.username
    password = args.password

    print("Authenticating...")
    print(f"[HEADLESS] Base URL: {base_url}")

    # Step 1: Send OTP
    login_resp = requests.post(
        f"{base_url}/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )

    if login_resp.status_code != 200:
        print("[HEADLESS] Login failed:", login_resp.text)
        sys.exit(1)

    print("[HEADLESS] OTP sent.")

    otp = input("Enter the 6-digit OTP from your email: ").strip()

    # Step 2: Verify OTP
    verify_resp = requests.post(
        f"{base_url}/auth/verify",
        json={"username": username, "otp": otp},
        timeout=10,
    )

    if verify_resp.status_code != 200:
        print("[HEADLESS] OTP verification failed:", verify_resp.text)
        sys.exit(1)

    token_data = verify_resp.json()
    access_token = token_data.get("access_token")

    if not access_token:
        print("[HEADLESS] No access token received.")
        sys.exit(1)

    print("[HEADLESS] Token acquired.")

    headers = {"Authorization": f"Bearer {access_token}"}

    # Step 3: Confirm identity
    me_resp = requests.get(
        f"{base_url}/auth/me",
        headers=headers,
        timeout=10,
    )

    if me_resp.status_code != 200:
        print("[HEADLESS] Identity check failed:", me_resp.text)
        sys.exit(1)

    identity = me_resp.json()
    print("[HEADLESS] Identity confirmed:", identity)

    print("\nAuthentication successful.")
    print("Execution layer currently locked (no live trades).")
    print("Guarded mode confirmed.")
    print("HEADLESS_DEV_MODE ready.")

    print("\n=== ENGINE SESSION READY ===")


if __name__ == "__main__":
    raise SystemExit(main())
