"""
backend/adapters/coinbase_adapter.py
Capital Strata Systems (CSS)

Coinbase Advanced Trade adapter (SDK-backed) with legacy-compatible helpers.

Why:
- Your prior custom signer produced 401 Unauthorized with CDP key files.
- The official Coinbase SDK handles CDP auth robustly.
- Existing CSS modules expect helper methods like get_accounts().

Contract:
- CoinbaseAdapter(keyfile=...)
- ._request(method, endpoint, params=None, data=None, json=None, headers=None)
- Legacy helper methods used by backend/adapters/coinbase_execution.py and tools.

Keyfile resolution order:
1) explicit keyfile arg
2) env var COINBASE_KEYFILE
3) repo-local default: .\keys\cdp_api_key (2).json
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs

try:
    from coinbase.rest import RESTClient
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "Missing dependency coinbase-advanced-py. Install in your venv:\n"
        "  pip install coinbase-advanced-py\n"
        f"Original import error: {e}"
    )


def _coerce(obj: Any) -> Any:
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return obj.to_dict()
    return obj


def _split_endpoint_and_params(endpoint: str) -> tuple[str, Dict[str, Any]]:
    if "?" not in endpoint:
        return endpoint, {}

    path, query = endpoint.split("?", 1)
    parsed = parse_qs(query, keep_blank_values=True)

    out: Dict[str, Any] = {}
    for k, v in parsed.items():
        if len(v) == 1:
            out[k] = v[0]
        else:
            out[k] = v
    return path, out


class CoinbaseAdapter:
    def __init__(self, keyfile: Optional[str] = None, *, verbose: Optional[bool] = None):
        self.keyfile = (
            keyfile
            or os.environ.get("COINBASE_KEYFILE")
            or os.path.join("keys", "cdp_api_key (2).json")
        )

        if verbose is None:
            verbose = os.environ.get("COINBASE_VERBOSE", "0").strip().lower() in ("1", "true", "yes")

        self._client = RESTClient(key_file=self.keyfile, verbose=bool(verbose))

    # -----------------------------
    # Core generic request surface
    # -----------------------------
    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        method_u = method.upper().strip()

        # Merge params from endpoint querystring + params argument
        path, qs_params = _split_endpoint_and_params(endpoint)
        merged_params: Dict[str, Any] = {}
        merged_params.update(qs_params)
        if params:
            merged_params.update(params)

        payload = json if json is not None else data

        try:
            if method_u == "GET":
                resp = self._client.get(path, params=merged_params or None)
            elif method_u == "POST":
                resp = self._client.post(path, data=payload or None, params=merged_params or None)
            elif method_u == "PUT":
                resp = self._client.put(path, data=payload or None, params=merged_params or None)
            elif method_u == "DELETE":
                resp = self._client.delete(path, params=merged_params or None)
            else:
                raise ValueError(f"Unsupported HTTP method: {method_u}")
        except Exception as e:
            raise RuntimeError(
                "CoinbaseAdapter request failed.\n"
                f"  method={method_u}\n"
                f"  endpoint={endpoint}\n"
                f"  keyfile={self.keyfile}\n"
                f"  error={e}"
            ) from e

        coerced = _coerce(resp)
        if isinstance(coerced, dict):
            return coerced
        return {"result": coerced}

    # -----------------------------------
    # Legacy-compatible helper methods
    # -----------------------------------
    def get_key_permissions(self) -> Dict[str, Any]:
        return self._request("GET", "/api/v3/brokerage/key_permissions")

    def get_accounts(self, *, limit: int = 250, cursor: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/api/v3/brokerage/accounts", params=params)

    def get_account(self, account_uuid: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/v3/brokerage/accounts/{account_uuid}")

    def get_products(self, *, product_type: Optional[str] = None, limit: int = 250) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit}
        if product_type:
            params["product_type"] = product_type
        return self._request("GET", "/api/v3/brokerage/products", params=params)

    def get_product(self, product_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/v3/brokerage/products/{product_id}")

    def list_open_orders(self, *, product_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        qs = {"order_status": "OPEN", "limit": limit}
        if product_id:
            qs["product_id"] = product_id
        return self._request("GET", "/api/v3/brokerage/orders/historical/batch", params=qs)

    def cancel_orders(self, order_ids: List[str]) -> Dict[str, Any]:
        # Coinbase endpoint supports batch cancel
        payload = {"order_ids": order_ids}
        return self._request("POST", "/api/v3/brokerage/orders/batch_cancel", json=payload)

    def create_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Caller should supply valid Advanced Trade order payload
        return self._request("POST", "/api/v3/brokerage/orders", json=payload)