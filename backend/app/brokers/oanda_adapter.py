"""
OANDA Broker Adapter (V20 REST)

Design goals:
- Minimal, reliable wiring for Phase 1.
- Works for PRACTICE and LIVE by switching OANDA_BASE_URL + token + account id.
- Fail-closed: missing config => not configured.
- Provides: get_account_summary(), place_order(), close_trade() for smoke tests.

Env vars expected:
- OANDA_API_KEY        (personal access token)
- OANDA_ACCOUNT_ID     (account id string, e.g. 101-001-... for practice)
- OANDA_BASE_URL       (https://api-fxpractice.oanda.com OR https://api-fxtrade.oanda.com)
Optional:
- OANDA_TIMEOUT_SECS   (default 15)
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


@dataclass(frozen=True)
class OandaConfig:
    base_url: str
    api_key: str
    account_id: str
    timeout_secs: int

    @staticmethod
    def from_env() -> "OandaConfig":
        base_url = _env("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
        api_key = _env("OANDA_API_KEY", "")
        account_id = _env("OANDA_ACCOUNT_ID", "")
        timeout = _env("OANDA_TIMEOUT_SECS", "15")
        try:
            timeout_i = int(timeout)
        except Exception:
            timeout_i = 15

        # normalize base url
        base_url = base_url.rstrip("/")

        return OandaConfig(
            base_url=base_url,
            api_key=api_key,
            account_id=account_id,
            timeout_secs=timeout_i,
        )


class OandaAdapter:
    """
    Small adapter used by:
    - backend.app.simulator (Phase 1 smoke test)
    - backend.app.run_live_guarded (guarded micro-trade harness)

    Keep the surface area small and predictable.
    """

    def __init__(self, config: Optional[OandaConfig] = None):
        self._cfg = config or OandaConfig.from_env()

    @property
    def name(self) -> str:
        return "oanda"

    def is_configured(self) -> bool:
        return bool(self._cfg.api_key and self._cfg.account_id and self._cfg.base_url)

    # -----------------------------
    # Internal HTTP helpers
    # -----------------------------
    def _headers(self) -> Dict[str, str]:
        # Do NOT print api key anywhere.
        return {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        # path can be "v3/accounts" or "/v3/accounts"
        p = path.lstrip("/")
        return f"{self._cfg.base_url}/{p}"

    def _request_json(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Tuple[bool, int, Dict[str, Any]]:
        """
        Returns (ok, http_status, json_dict).
        If non-JSON response, json_dict contains {"raw": "..."}.
        """
        if not self.is_configured():
            raise RuntimeError("OANDA not configured: set OANDA_API_KEY, OANDA_ACCOUNT_ID and OANDA_BASE_URL.")

        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(
            self._url(path),
            data=data,
            method=method.upper(),
            headers=self._headers(),
        )

        try:
            with urllib.request.urlopen(req, timeout=self._cfg.timeout_secs) as resp:
                status = getattr(resp, "status", 200)
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    j = json.loads(raw) if raw else {}
                except Exception:
                    j = {"raw": raw}
                return True, int(status), j

        except urllib.error.HTTPError as e:
            status = int(getattr(e, "code", 0) or 0)
            raw = ""
            try:
                raw = e.read().decode("utf-8", errors="replace")
            except Exception:
                raw = ""
            try:
                j = json.loads(raw) if raw else {}
            except Exception:
                j = {"raw": raw}
            return False, status, j

        except Exception as e:
            return False, 0, {"error": str(e)}

    # -----------------------------
    # Public API used by our tests
    # -----------------------------
    def get_account_summary(self) -> Dict[str, Any]:
        """
        Returns a normalized summary:
        { ok, status, balance, nav, currency, raw }
        """
        ok, status, j = self._request_json("GET", f"v3/accounts/{self._cfg.account_id}/summary")

        # OANDA returns numeric fields as strings
        acct = (j.get("account") or {}) if isinstance(j, dict) else {}
        balance = acct.get("balance")
        nav = acct.get("NAV") or acct.get("nav")
        currency = acct.get("currency")

        def _to_float(x: Any) -> Optional[float]:
            try:
                if x is None:
                    return None
                return float(x)
            except Exception:
                return None

        return {
            "ok": bool(ok),
            "status": int(status),
            "balance": _to_float(balance),
            "nav": _to_float(nav),
            "currency": currency,
            "raw": j,
        }

    def place_order(
        self,
        symbol: Optional[str] = None,
        units: int = 1,
        side: str = "BUY",
        order_type: str = "MARKET",
        *,
        instrument: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Places a basic MARKET order (FOK). Returns normalized order result.

        Accepts either:
          - symbol="EUR_USD"  (preferred in our engine)
          - instrument="EUR_USD" (compat with earlier harness)
        side:
          - BUY  -> positive units
          - SELL -> negative units
        """
        # tolerate either arg name
        instrument_final = (symbol or instrument or "").strip()
        if not instrument_final:
            return {"ok": False, "broker": "oanda", "error": "Missing instrument/symbol."}

        side_u = (side or "BUY").upper().strip()
        signed_units = int(units)
        if side_u == "SELL":
            signed_units = -abs(signed_units)
        else:
            signed_units = abs(signed_units)

        order_payload = {
            "order": {
                "type": order_type.upper(),
                "instrument": instrument_final,
                "units": str(signed_units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }

        ok, status, j = self._request_json("POST", f"v3/accounts/{self._cfg.account_id}/orders", body=order_payload)

        # Extract order_id / trade_id best-effort from common fields
        order_id = None
        trade_id = None

        if isinstance(j, dict):
            fill = j.get("orderFillTransaction") or {}
            create = j.get("orderCreateTransaction") or {}
            order_id = (fill.get("orderID") or create.get("id") or create.get("orderID") or fill.get("id"))

            # OANDA fill transaction often contains tradeOpened / tradeReduced etc.
            trade_opened = fill.get("tradeOpened") or {}
            trade_reduced = fill.get("tradeReduced") or {}
            trade_id = trade_opened.get("tradeID") or trade_reduced.get("tradeID") or fill.get("tradeID")

        return {
            "ok": bool(ok),
            "status": int(status),
            "broker": "oanda",
            "symbol": instrument_final,
            "side": side_u,
            "units": abs(int(units)),
            "order_id": order_id,
            "trade_id": trade_id,
            "error": "" if ok else (j.get("errorMessage") if isinstance(j, dict) else "Order failed"),
            "raw": j,
        }

    def close_trade(self, trade_id: str) -> Dict[str, Any]:
        """
        Close a trade by trade_id.
        """
        tid = (trade_id or "").strip()
        if not tid:
            return {"ok": False, "broker": "oanda", "error": "Missing trade_id."}

        ok, status, j = self._request_json(
            "PUT",
            f"v3/accounts/{self._cfg.account_id}/trades/{tid}/close",
            body={"units": "ALL"},
        )

        return {
            "ok": bool(ok),
            "status": int(status),
            "broker": "oanda",
            "trade_id": tid,
            "error": "" if ok else (j.get("errorMessage") if isinstance(j, dict) else "Close failed"),
            "raw": j,
        }
