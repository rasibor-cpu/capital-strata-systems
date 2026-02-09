# backend/app/brokers/oanda_adapter.py
from __future__ import annotations

import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from .base import BrokerAdapter, OrderRequest, OrderResult


class OandaAdapter(BrokerAdapter):
    """
    Paper/Practice OANDA adapter.
    Uses standard library urllib to avoid extra dependencies.
    """

    name = "oanda"

    def __init__(self) -> None:
        self.api_key = os.getenv("OANDA_API_KEY", "").strip()
        self.account_id = os.getenv("OANDA_ACCOUNT_ID", "").strip()
        # practice by default (safe)
        self.base_url = os.getenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com").strip()

    def is_configured(self) -> bool:
        return bool(self.api_key and self.account_id and self.base_url)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def place_order(self, req: OrderRequest) -> OrderResult:
        if not self.is_configured():
            return OrderResult(
                ok=False,
                broker=self.name,
                symbol=req.symbol,
                side=req.side,
                units=req.units,
                error="OANDA not configured: set OANDA_API_KEY, OANDA_ACCOUNT_ID (practice) and optionally OANDA_BASE_URL.",
            )

        # OANDA: units sign determines buy/sell
        units = int(req.units)
        if req.side.lower() == "sell":
            units = -abs(units)
        else:
            units = abs(units)

        payload: Dict[str, Any] = {
            "order": {
                "units": str(units),
                "instrument": req.symbol,
                "timeInForce": "FOK",
                "type": "MARKET",
                "positionFill": "DEFAULT",
            }
        }
        if req.client_tag:
            payload["order"]["clientExtensions"] = {"tag": req.client_tag}

        url = f"{self.base_url}/v3/accounts/{self.account_id}/orders"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")

        try:
            with urllib.request.urlopen(request, timeout=20) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                raw = json.loads(body) if body else {}
                order_id: Optional[str] = None

                # best-effort extraction
                if isinstance(raw, dict):
                    order_id = (
                        raw.get("orderCreateTransaction", {}) or {}
                    ).get("id") or (
                        raw.get("orderFillTransaction", {}) or {}
                    ).get("id")

                return OrderResult(
                    ok=True,
                    broker=self.name,
                    symbol=req.symbol,
                    side=req.side,
                    units=req.units,
                    order_id=order_id,
                    raw=raw,
                )

        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            return OrderResult(
                ok=False,
                broker=self.name,
                symbol=req.symbol,
                side=req.side,
                units=req.units,
                error=f"HTTPError {getattr(e, 'code', 'unknown')}: {body or str(e)}",
            )
        except Exception as e:
            return OrderResult(
                ok=False,
                broker=self.name,
                symbol=req.symbol,
                side=req.side,
                units=req.units,
                error=str(e),
            )
