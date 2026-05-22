
"""
Capital Strata Systems (CSS)
Coinbase Broker Adapter
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests


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
        self.api_key_name = str(api_key_name or "").strip()
        self.api_private_key_path = str(api_private_key_path or "").strip()
        self.paper_mode = bool(paper_mode)
        self.timeout_seconds = int(timeout_seconds or 10)
        self._client: Optional[Any] = None

    def is_configured(self) -> bool:
        if self.paper_mode:
            return True

        return bool(self.api_private_key_path)

    def connect(self) -> bool:
        if self.paper_mode:
            return True

        if not self.is_configured():
            raise RuntimeError(
                "Coinbase live adapter missing key file."
            )

        self._client = self._build_client()
        return True

    def _build_client(self) -> Any:
        from coinbase.rest import RESTClient

        return RESTClient(
            key_file=self.api_private_key_path,
        )

    def _client_or_connect(self) -> Any:
        if self._client is None:
            self.connect()

        return self._client

    # -------------------------------------------------
    # MARKET DATA
    # -------------------------------------------------

    def get_candles(
        self,
        product_id: str,
        granularity_name: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        granularity = GRANULARITY_MAP.get(granularity_name)

        if granularity is None:
            raise ValueError(
                f"Unsupported granularity: {granularity_name}"
            )

        url = COINBASE_CANDLES_URL.format(
            product_id=product_id
        )

        params = {
            "granularity": granularity,
        }

        resp = requests.get(
            url,
            params=params,
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

    # -------------------------------------------------
    # ACCOUNT / BALANCE
    # -------------------------------------------------

    def get_account(self) -> Dict[str, Any]:
        return self.get_account_summary()

    def get_balance(self) -> Dict[str, Any]:
        return self.get_account_summary()

    def fetch_balance(self) -> Dict[str, Any]:
        return self.get_account_summary()

    def get_account_summary(self) -> Dict[str, Any]:
        if self.paper_mode:
            return {
                "mode": "paper",
                "balance": 0.0,
                "equity": 0.0,
                "balance_usd": 0.0,
                "currency": "USD",
                "source": "COINBASE_PAPER",
                "ok": True,
            }

        client = self._client_or_connect()

        response = client.get_accounts()

        accounts = []

        if hasattr(response, "accounts"):
            accounts = response.accounts

        elif isinstance(response, dict):
            accounts = response.get("accounts", [])

        usd_equivalent_balance = 0.0

        for account in accounts:
            try:
                if isinstance(account, dict):
                    currency = str(
                        account.get("currency", "")
                    ).upper()

                    available_balance = account.get(
                        "available_balance",
                        {},
                    )

                else:
                    currency = str(
                        getattr(
                            account,
                            "currency",
                            "",
                        )
                    ).upper()

                    available_balance = getattr(
                        account,
                        "available_balance",
                        {},
                    )

                value = None

                if isinstance(
                    available_balance,
                    dict,
                ):
                    value = available_balance.get(
                        "value"
                    )

                else:
                    value = getattr(
                        available_balance,
                        "value",
                        None,
                    )

                print(
                    "[COINBASE PARSE DEBUG]",
                    "currency=",
                    currency,
                    "value=",
                    value,
                )

                if currency not in {
                    "USD",
                    "USDC",
                }:
                    continue

                if value is None:
                    continue

                usd_equivalent_balance += float(value)

            except Exception as exc:
                print(
                    "[COINBASE ACCOUNT PARSE ERROR]",
                    exc,
                )

        print(
            "[COINBASE FINAL USD BALANCE]",
            usd_equivalent_balance,
        )

        return {
            "mode": "live",
            "balance": float(
                usd_equivalent_balance
            ),
            "equity": float(
                usd_equivalent_balance
            ),
            "balance_usd": float(
                usd_equivalent_balance
            ),
            "currency": "USD_EQUIVALENT",
            "source": "COINBASE_LIVE_ACCOUNT",
            "ok": True,
        }

    # -------------------------------------------------
    # EXECUTION
    # -------------------------------------------------

    def place_market_buy(
        self,
        *,
        product_id: str,
        size_usd: float,
    ) -> Dict[str, Any]:
        if self.paper_mode:
            return {
                "status": "paper_filled",
                "product_id": product_id,
                "size_usd": size_usd,
            }

        raise NotImplementedError(
            "Live Coinbase execution remains governed outside this adapter."
        )

    def place_market_sell(
        self,
        *,
        product_id: str,
        size_asset: float,
    ) -> Dict[str, Any]:
        if self.paper_mode:
            return {
                "status": "paper_filled",
                "product_id": product_id,
                "size_asset": size_asset,
            }

        raise NotImplementedError(
            "Live Coinbase execution remains governed outside this adapter."
        )
