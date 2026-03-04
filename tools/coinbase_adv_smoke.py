# tools/coinbase_adv_smoke.py
from __future__ import annotations

import glob
import json
import os
import sys
import requests

from coinbase.jwt_generator import build_rest_jwt, format_jwt_uri


def _find_keyfile(repo_root: str) -> str:
    # Try common patterns/extensions
    patterns = [
        os.path.join(repo_root, "cdp_api_key (2).json"),
        os.path.join(repo_root, "cdp_api_key (2).txt"),
        os.path.join(repo_root, "cdp_api_key (2)"),
        os.path.join(repo_root, "cdp_api_key*.json"),
        os.path.join(repo_root, "cdp_api_key*.txt"),
        os.path.join(repo_root, "cdp_api_key*"),
    ]
    for pat in patterns:
        matches = glob.glob(pat)
        if matches:
            # pick the newest
            matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return matches[0]
    return ""


def _pick(d: dict, keys: list[str]) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def main() -> int:
    repo_root = os.getcwd()
    key_path = _find_keyfile(repo_root)
    if not key_path:
        print("ERROR: Could not find Coinbase CDP key file in repo root.")
        print("Expected something like: cdp_api_key (2).json or .txt")
        return 1

    print("Using key file:", os.path.basename(key_path))

    # Read raw text first (some files are .txt but contain JSON)
    with open(key_path, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    if not raw.startswith("{"):
        print("ERROR: Key file does not look like JSON (does not start with '{').")
        print("First 40 chars:", raw[:40])
        return 2

    data = json.loads(raw)

    key_name = _pick(data, ["name", "key_name", "keyName", "kid", "api_key_name"])
    private_key = _pick(data, ["private_key", "privateKey", "privateKeyPem", "private_key_pem"])

    if not key_name:
        print("ERROR: Could not find key name field in JSON.")
        print("Top-level keys:", sorted(list(data.keys()))[:50])
        return 3

    if not private_key:
        print("ERROR: Could not find private key field in JSON.")
        print("Top-level keys:", sorted(list(data.keys()))[:50])
        return 4

    # Normalize escaped newlines if stored as "\\n"
    private_key = private_key.replace("\\n", "\n").strip() + "\n"

    # Quick sanity check: must contain PEM header/footer
    if "BEGIN" not in private_key or "END" not in private_key:
        print("ERROR: Private key found, but it does not look like PEM.")
        print("Private key first line:", private_key.splitlines()[0] if private_key else "")
        return 5

    method = "GET"
    path = "/api/v3/brokerage/accounts"
    url = f"https://api.coinbase.com{path}"

    uri = format_jwt_uri(method, path)
    token = build_rest_jwt(uri, key_name, private_key)

    r = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "CSS-CoinbaseAdvSmoke/1.0",
        },
        timeout=30,
    )

    print("HTTP:", r.status_code)
    if r.status_code != 200:
        try:
            print(r.json())
        except Exception:
            print(r.text[:800])
        return 6

    payload = r.json()
    accounts = payload.get("accounts", []) if isinstance(payload, dict) else []
    print("Accounts returned:", len(accounts))
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())