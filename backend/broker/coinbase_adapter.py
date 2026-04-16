"""
Capital Strata Systems (CSS)
Coinbase Broker Adapter

Scope:
- Public candles endpoint
- Coinbase Advanced Trade JWT auth
- Live account retrieval
- Live product lookup
- Live market buy/sell order submission
- Paper-mode fallback preserved

Credential support:
1) Preferred existing repo format:
   COINBASE_CDP_KEY_NAME=...
   COINBASE_CDP_PRIVATE_KEY_PATH=coinbase_private_key.pem

2) Optional inline format:
   COINBASE_KEY_NAME=...
   COINBASE_PRIVATE_KEY="-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----"
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import jwt
import requests
from dotenv import load_dotenv


load_dotenv()

COINBASE_API_BASE = "https://api.coinbase.com/api/v3/brokerage"
COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"

GRANULARITY_MAP = {
    "ONE_MINUTE": 60,
    "FIVE_MINUTE": 300,
    "FIFTEEN_MINUTE": 900,
    "ONE_HOUR": 3600,
    "SIX_HOUR": 21600,
    "ONE_DAY": 86400,
}


class CoinbaseAdapter:
    def __init__(
        self,
        *,
        api_key_name: str = "",
        api_private_key: str = "",
        api_private_key_path: str = "",
        paper_mode: bool = True,
        timeout_seconds: int = 10,
    ) -> None:
        self.api_key_name = api_key_name or self._resolve_key_name()
        self.api_private_key = api_private_key or self._resolve_private_key(
            explicit_path=api_private_key_path
        )
        self.paper_mode = paper_mode
        self.timeout_seconds = timeout_seconds

    # =========================================================
    # ENV / KEY RESOLUTION
    # =========================================================

    def _resolve_key_name(self) -> str:
        return (
            os.getenv("COINBASE_CDP_KEY_NAME", "").strip()
            or os.getenv("COINBASE_KEY_NAME", "").strip()
        )

    def _resolve_private_key(self, explicit_path: str = "") -> str:
        inline_key = os.getenv("COINBASE_PRIVATE_KEY", "").strip()
        if inline_key:
            return inline_key.replace("\\n", "\n").strip()

        pem_path = (
            explicit_path.strip()
            or os.getenv("COINBASE_CDP_PRIVATE_KEY_PATH", "").strip()
        )
        if not pem_path:
            return ""

        path_obj = Path(pem_path)
        if not path_obj.is_absolute():
            path_obj = Path.cwd() / pem_path

        if not path_obj.exists():
            return ""

        return path_obj.read_text(encoding="utf-8").strip()

    def _validate_live_credentials(self) -> None:
        if not self.api_key_name or not self.api_private_key:
            raise ValueError("Missing Coinbase API credentials")

    # =========================================================
    # JWT AUTH
    # =========================================================

    def _build_jwt(self) -> str:
        """
        Build Coinbase CDP JWT Bearer token.

        Note:
        This implementation is designed for the user's current CSS setup.
        If Coinbase changes JWT claim requirements, auth may need a small update.
        """
        self._validate_live_credentials()

        now = int(time.time())
        payload = {
            "sub": self.api_key_name,
            "iss": "cdp",
            "nbf": now,
            "exp": now + 120,
        }

        token = jwt.encode(
            payload,
            self.api_private_key,
            algorithm="ES256",
            headers={
                "kid": self.api_key_name,
                "nonce": str(uuid.uuid4()),
            },
        )

        if isinstance(token, bytes):
            token = token.decode("utf-8")

        return token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._build_jwt()}",
            "Content-Type": "application/json",
        }

    # =========================================================
    # MARKET DATA
    # =========================================================

    def get_candles(
        self,
        product_id: str,
        granularity_name: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        granularity = GRANULARITY_MAP.get(granularity_name)
        if granularity is None:
            raise ValueError(f"Unsupported granularity: {granularity_name}")

        url = COINBASE_CANDLES_URL.format(product_id=product_id)
        params = {"granularity": granularity}

        resp = requests.get(url, params=params, timeout=self.timeout_seconds)
        resp.raise_for_status()

        raw = resp.json()
        raw.reverse()

        candles: List[Dict[str, Any]] = []
        for item in raw[-limit:]:
            ts, low, high, open_, close, volume = item
            candles.append(
                {
                    "ts": ts,
                    "low": float(low),
                    "high": float(high),
                    "open": float(open_),
                    "close": float(close),
                    "volume": float(volume),
                }
            )

        return candles
    # =========================================================
    # ACCOUNT ACCESS
    # =========================================================

    def list_accounts(self) -> Dict[str, Any]:
        if self.paper_mode:
            return {
                "mode": "paper",
                "accounts": [],
            }

        url = f"{COINBASE_API_BASE}/accounts"
        resp = requests.get(
            url,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def get_account(self) -> Dict[str, Any]:
        if self.paper_mode:
            return {
                "mode": "paper",
                "balance_usd": 0.0,
            }

        data = self.list_accounts()
        total_usd = 0.0
        balances: List[Dict[str, Any]] = []

        for acct in data.get("accounts", []):
            available_balance = acct.get("available_balance", {}) or {}
            value = available_balance.get("value", "0")
            currency = available_balance.get("currency", "")

            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                numeric_value = 0.0

            balances.append(
                {
                    "uuid": acct.get("uuid", ""),
                    "currency": currency,
                    "available": numeric_value,
                    "name": acct.get("name", ""),
                    "type": acct.get("type", ""),
                }
            )

            if currency in {"USD", "USDC"}:
                total_usd += numeric_value

        return {
            "mode": "live",
            "balance_usd": total_usd,
            "balances": balances,
            "raw": data,
        }

    def get_product(self, product_id: str) -> Dict[str, Any]:
        if self.paper_mode:
            return {
                "product_id": product_id,
                "status": "paper_valid",
            }

        url = f"{COINBASE_API_BASE}/products/{product_id}"
        resp = requests.get(
            url,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    # =========================================================
    # ORDERS
    # =========================================================

    def place_market_buy(
        self,
        *,
        product_id: str,
        size_usd: float,
    ) -> Dict[str, Any]:
        if size_usd <= 0:
            raise ValueError("size_usd must be positive")

        if self.paper_mode:
            return {
                "status": "paper_filled",
                "product_id": product_id,
                "size_usd": size_usd,
            }

        url = f"{COINBASE_API_BASE}/orders"
        payload = {
            "client_order_id": str(uuid.uuid4()),
            "product_id": product_id,
            "side": "BUY",
            "order_configuration": {
                "market_market_ioc": {
                    "quote_size": str(size_usd),
                }
            },
        }

        resp = requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def place_market_sell(
        self,
        *,
        product_id: str,
        size_asset: float,
    ) -> Dict[str, Any]:
        if size_asset <= 0:
            raise ValueError("size_asset must be positive")

        if self.paper_mode:
            return {
                "status": "paper_filled",
                "product_id": product_id,
                "size_asset": size_asset,
            }

        url = f"{COINBASE_API_BASE}/orders"
        payload = {
            "client_order_id": str(uuid.uuid4()),
            "product_id": product_id,
            "side": "SELL",
            "order_configuration": {
                "market_market_ioc": {
                    "base_size": str(size_asset),
                }
            },
        }

        resp = requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        if not order_id:
            raise ValueError("order_id is required")

        if self.paper_mode:
            return {
                "order_id": order_id,
                "status": "paper_filled",
            }

        url = f"{COINBASE_API_BASE}/orders/historical/{order_id}"
        resp = requests.get(
            url,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def ping_live_auth(self) -> Dict[str, Any]:
        """
        Small helper for auth verification without placing trades.
        """
        if self.paper_mode:
            return {"mode": "paper", "ok": True}

        data = self.list_accounts()
        return {
            "mode": "live",
            "ok": True,
            "account_count": len(data.get("accounts", [])),
        }