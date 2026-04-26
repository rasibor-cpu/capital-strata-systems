from __future__ import annotations

import json
import time
from typing import Optional

import jwt  # PyJWT
import requests


class CoinbaseBalanceFetcher:
    """
    Fetch real Coinbase account balance using CDP/Advanced Trade PEM authentication.

    Important Coinbase JWT rule:
    REST request URI must include method + host + path, for example:
    "GET api.coinbase.com/api/v3/brokerage/accounts"
    """

    BASE_URL = "https://api.coinbase.com"
    HOST = "api.coinbase.com"

    def __init__(self, key_name: str, private_key_path: str):
        self.key_name = (key_name or "").strip()
        self.private_key_path = private_key_path

        with open(private_key_path, "r", encoding="utf-8") as f:
            self.private_key = f.read().strip()

    def _build_jwt(self, method: str, path: str) -> str:
        method = method.upper().strip()
        path = path.strip()

        # Coinbase REST JWT expects host included in uri.
        uri = f"{method} {self.HOST}{path}"

        now = int(time.time())

        payload = {
            "sub": self.key_name,
            "iss": "cdp",
            "nbf": now,
            "exp": now + 120,
            "uri": uri,
        }

        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="ES256",
            headers={
                "kid": self.key_name,
                "nonce": str(now),
            },
        )

        return token

    def get_balance(self) -> Optional[float]:
        try:
            path = "/api/v3/brokerage/accounts"
            token = self._build_jwt("GET", path)

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            resp = requests.get(self.BASE_URL + path, headers=headers, timeout=15)

            if resp.status_code != 200:
                print(f"[COINBASE BALANCE ERROR] HTTP {resp.status_code}")
                try:
                    print(f"[COINBASE BALANCE DETAIL] {resp.text[:300]}")
                except Exception:
                    pass
                return None

            data = resp.json()
            total = 0.0

            for acct in data.get("accounts", []):
                bal = acct.get("available_balance", {}).get("value")
                if bal not in (None, ""):
                    try:
                        total += float(bal)
                    except (TypeError, ValueError):
                        continue

            return round(total, 2)

        except Exception as e:
            print(f"[COINBASE BALANCE ERROR] {e}")
            return None
