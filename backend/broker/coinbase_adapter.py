"""
Capital Strata Systems (CSS)
Coinbase Broker Adapter

Read-only balance + public candles adapter.
Live order execution remains blocked unless explicitly implemented elsewhere.
"""

from __future__ import annotations

import glob
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from coinbase.rest import RESTClient  # type: ignore
except Exception:
    RESTClient = None  # type: ignore


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
        api_private_key_path: str = "",
        paper_mode: bool = True,
        timeout_seconds: int = 10,
    ) -> None:
        self.api_key_name = api_key_name
        self.api_private_key_path = api_private_key_path
        self.paper_mode = paper_mode
        self.timeout_seconds = timeout_seconds

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
        resp = requests.get(
            url,
            params={"granularity": granularity},
            timeout=self.timeout_seconds,
        )
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

    def place_market_buy(self, *, product_id: str, size_usd: float) -> Dict[str, Any]:
        if self.paper_mode:
            return {
                "status": "paper_filled",
                "product_id": product_id,
                "size_usd": size_usd,
            }

        raise NotImplementedError("Live Coinbase execution not enabled in active adapter.")

    def place_market_sell(self, *, product_id: str, size_asset: float) -> Dict[str, Any]:
        if self.paper_mode:
            return {
                "status": "paper_filled",
                "product_id": product_id,
                "size_asset": size_asset,
            }

        raise NotImplementedError("Live Coinbase execution not enabled in active adapter.")

    def _candidate_json_paths(self) -> List[str]:
        candidates: List[str] = []

        for key in (
            "COINBASE_KEY_JSON_PATH",
            "COINBASE_KEY_JSON",
            "COINBASE_KEY_FILE",
        ):
            value = os.getenv(key)
            if value:
                candidates.append(value)

        if self.api_private_key_path and self.api_private_key_path.lower().endswith(".json"):
            candidates.append(self.api_private_key_path)

        repo_keys = os.path.join(os.getcwd(), "keys")
        candidates.extend(glob.glob(os.path.join(repo_keys, "cdp_api_key*.json")))
        candidates.extend(glob.glob(os.path.join(repo_keys, "cdp_api-key*.json")))

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        candidates.extend(glob.glob(os.path.join(downloads, "cdp_api_key*.json")))
        candidates.extend(glob.glob(os.path.join(downloads, "cdp_api-key*.json")))

        existing: List[str] = []
        for path in candidates:
            normalized = str(path).strip().strip('"')
            if normalized and os.path.exists(normalized):
                existing.append(normalized)

        existing.sort(key=lambda path: os.path.getmtime(path), reverse=True)

        seen = set()
        ordered: List[str] = []
        for path in existing:
            if path not in seen:
                seen.add(path)
                ordered.append(path)

        return ordered

    def _auto_load_from_cdp_json(self) -> Tuple[Optional[str], Optional[str]]:
        for path in self._candidate_json_paths():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                key_name = data.get("name") or data.get("key_name")
                private_key = data.get("privateKey") or data.get("private_key")

                if key_name and private_key:
                    return str(key_name), str(private_key)
            except Exception:
                continue

        return None, None

    def _get_rest_client(self):
        if RESTClient is None:
            raise RuntimeError("Coinbase RESTClient unavailable")

        api_key = ""
        api_secret = ""

        if self.api_private_key_path and self.api_private_key_path.lower().endswith(".json"):
            api_key, api_secret = self._auto_load_from_cdp_json()

        if not api_key or not api_secret:
            api_key = (
                os.getenv("COINBASE_API_KEY")
                or os.getenv("COINBASE_CDP_KEY_NAME")
                or os.getenv("COINBASE_KEY_NAME")
                or self.api_key_name
                or ""
            )

            api_secret = (
                os.getenv("COINBASE_API_SECRET")
                or os.getenv("COINBASE_CDP_PRIVATE_KEY")
                or os.getenv("COINBASE_PRIVATE_KEY")
                or ""
            )

            if self.api_private_key_path and "BEGIN" in self.api_private_key_path:
                api_secret = api_secret or self.api_private_key_path

        if not api_key or not api_secret:
            api_key, api_secret = self._auto_load_from_cdp_json()

        if not api_key or not api_secret:
            raise RuntimeError("Coinbase credentials unavailable for read-only balance")

        return RESTClient(api_key=api_key, api_secret=api_secret)

    @staticmethod
    def _to_dict(obj: Any) -> Any:
        if obj is None:
            return None

        if isinstance(obj, (dict, list, str, int, float, bool)):
            return obj

        if hasattr(obj, "to_dict"):
            try:
                return obj.to_dict()
            except Exception:
                pass

        if hasattr(obj, "__dict__"):
            try:
                return {
                    k: CoinbaseAdapter._to_dict(v)
                    for k, v in vars(obj).items()
                    if not k.startswith("_")
                }
            except Exception:
                pass

        return obj

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

    def get_accounts(self) -> List[Dict[str, Any]]:
        if self.paper_mode:
            return []

        client = self._get_rest_client()
        payload = self._to_dict(client.get_accounts())

        if isinstance(payload, dict):
            accounts = payload.get("accounts") or payload.get("data") or []
        elif isinstance(payload, list):
            accounts = payload
        else:
            accounts = []

        return [acct for acct in accounts if isinstance(acct, dict)]

    def get_account_balance(self) -> Dict[str, Any]:
        if self.paper_mode:
            return {
                "mode": "paper",
                "balance": 0.0,
                "equity": 0.0,
                "source": "COINBASE_PAPER",
                "account_count": 0,
            }

        accounts = self.get_accounts()
        total = 0.0

        for account in accounts:
            available = account.get("available_balance") or account.get("balance") or {}
            if isinstance(available, dict):
                value = available.get("value") or available.get("amount")
            else:
                value = available

            total += self._to_float(value)

        return {
            "mode": "live",
            "balance": float(total),
            "equity": float(total),
            "source": "COINBASE",
            "account_count": len(accounts),
        }

    def get_balance(self) -> Dict[str, Any]:
        return self.get_account_balance()

    def get_account(self) -> Dict[str, Any]:
        return self.get_account_balance()