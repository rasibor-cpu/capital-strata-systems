"""
tools/check_open_orders.py
Capital Strata Systems (CSS)

List OPEN Coinbase Advanced orders.

Usage:
  python tools/check_open_orders.py KEYFILE.json
  python tools/check_open_orders.py KEYFILE.json BTC-USD
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import importlib.util


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _find_adapter(repo: Path) -> Path:
    hits = list(repo.rglob("coinbase_adapter.py"))
    if not hits:
        raise FileNotFoundError("coinbase_adapter.py not found in repo.")
    hits.sort(key=lambda p: len(p.parts))
    return hits[0]


def _load_adapter(adapter_path: Path):
    spec = importlib.util.spec_from_file_location("css_coinbase_adapter", adapter_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module.CoinbaseAdapter


def _as_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def _extract_orders(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("orders", "order", "data", "results"):
        if key in resp:
            return _as_list(resp.get(key))
    return []


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/check_open_orders.py KEYFILE.json [PRODUCT_ID]")
        return 1

    keyfile = sys.argv[1]
    product_id: Optional[str] = None
    if len(sys.argv) > 2:
        product_id = sys.argv[2].upper()

    repo = _repo_root()
    adapter_path = _find_adapter(repo)
    CoinbaseAdapter = _load_adapter(adapter_path)

    adapter = CoinbaseAdapter(keyfile)

    qs = "order_status=OPEN&limit=100"
    if product_id:
        qs += f"&product_id={product_id}"

    endpoint = f"/api/v3/brokerage/orders/historical/batch?{qs}"
    resp = adapter._request("GET", endpoint)

    orders = _extract_orders(resp)

    print("\n=== CSS Coinbase Open Orders ===")
    print(f"Adapter file: {adapter_path}")
    print(f"Open orders: {len(orders)}\n")

    for o in orders:
        oid = o.get("order_id") or o.get("id")
        pid = o.get("product_id")
        side = o.get("side")
        status = o.get("status") or o.get("order_status")

        print(f"- order_id={oid} product={pid} side={side} status={status}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())