from __future__ import annotations

"""
OANDA v20 broker adapter (MANUAL-CONFIRM ONLY)

Hard guarantees:
- NO auto-trading
- NO background execution
- Orders are sent ONLY after explicit user confirmation
- Credentials via environment variables only

Required env vars:
- OANDA_ACCOUNT_ID
- OANDA_TOKEN

Optional:
- OANDA_ENV = practice | live
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import json
import os
import urllib.request
import urllib.error


# =========================
# Config object
# =========================

@dataclass(frozen=True)
class OandaConfig:
    environment: str
    api_url_practice: str
    api_url_live: str
    account_id_env: str = "OANDA_ACCOUNT_ID"
    token_env: str = "OANDA_TOKEN"

    def api_url(self) -> str:
        env_override = (os.environ.get("OANDA_ENV") or "").strip().lower()
        env_final = env_override or self.environment.lower()
        return self.api_url_live if env_final == "live" else self.api_url_practice

    def account_id(self) -> str:
        v = (os.environ.get(self.account_id_env) or "").strip()
        if not v:
            raise RuntimeError(f"Missing env var: {self.account_id_env}")
        return v

    def token(self) -> str:
        v = (os.environ.get(self.token_env) or "").strip()
        if not v:
            raise RuntimeError(f"Missing env var: {self.token_env}")
        return v


# =========================
# OANDA client
# =========================

class OandaClient:
    def __init__(self, cfg: OandaConfig) -> None:
        self.cfg = cfg

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = self.cfg.api_url().rstrip("/") + path

        headers = {
            "Authorization": f"Bearer {self.cfg.token()}",
            "Content-Type": "application/json"
        }

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url=url,
            data=data,
            headers=headers,
            method=method.upper()
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}

        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"OANDA HTTP {e.code} {e.reason} :: {msg}"
            ) from e

        except urllib.error.URLError as e:
            raise RuntimeError(f"OANDA connection error :: {e}") from e

    # =========================
    # Pricing
    # =========================

    def get_prices(self, instruments_csv: str) -> Dict[str, Any]:
        """
        instruments_csv example: "EUR_USD,GBP_USD,USD_JPY"
        """
        aid = self.cfg.account_id()
        path = f"/v3/accounts/{aid}/pricing?instruments={instruments_csv}"
        return self._request("GET", path)

    # =========================
    # Trading (manual confirm only)
    # =========================

    def place_market_order(
        self,
        instrument: str,
        units: int,
        side: str,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        side: 'buy' or 'sell'
        units: positive integer (sell is converted internally)
        """

        side = side.lower().strip()
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")

        if units <= 0:
            raise ValueError("units must be > 0")

        signed_units = units if side == "buy" else -units
        aid = self.cfg.account_id()

        order: Dict[str, Any] = {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(signed_units),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT"
        }

        if stop_loss_price is not None:
            order["stopLossOnFill"] = {
                "price": f"{stop_loss_price:.6f}"
            }

        if take_profit_price is not None:
            order["takeProfitOnFill"] = {
                "price": f"{take_profit_price:.6f}"
            }

        body = {"order": order}
        path = f"/v3/accounts/{aid}/orders"

        return self._request("POST", path, body)