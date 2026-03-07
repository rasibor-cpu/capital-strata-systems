from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests


ROOT = Path(__file__).resolve().parents[1]

SPOT_FILE = ROOT / "backend" / "state" / "spot_position.json"
ACCOUNT_FILE = ROOT / "backend" / "state" / "account_state.json"

INTERVAL = 30
COINBASE_URL = "https://api.exchange.coinbase.com/products/{product_id}/ticker"


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_live_price(product_id: str) -> float:
    url = COINBASE_URL.format(product_id=product_id)
    r = requests.get(
        url,
        timeout=10,
        headers={"User-Agent": "css-live-price-updater/1.0"},
    )
    r.raise_for_status()
    data = r.json()
    return safe_float(data.get("price"))


def update_prices() -> None:
    spot = load_json(SPOT_FILE)
    acct = load_json(ACCOUNT_FILE)

    positions = spot.get("positions", [])
    if not isinstance(positions, list):
        positions = []

    cash = safe_float(
        acct.get("cash")
        or acct.get("cash_usd")
        or acct.get("available_cash")
        or 0.0
    )

    total_market = 0.0
    total_unreal = 0.0

    for p in positions:
        product_id = str(
            p.get("product_id")
            or p.get("asset")
            or p.get("symbol")
            or "UNKNOWN"
        ).upper()

        qty = safe_float(p.get("quantity") or p.get("qty") or 0.0)
        entry = safe_float(p.get("entry_price") or p.get("avg_entry") or 0.0)
        side = str(p.get("side") or "LONG").upper()

        if qty <= 0:
            continue

        live_price = fetch_live_price(product_id)
        market_value = qty * live_price

        if side == "SHORT":
            unreal = (entry - live_price) * qty
            unreal_pct = ((entry - live_price) / entry * 100.0) if entry > 0 else 0.0
        else:
            unreal = (live_price - entry) * qty
            unreal_pct = ((live_price - entry) / entry * 100.0) if entry > 0 else 0.0

        p["asset"] = product_id
        p["symbol"] = product_id
        p["product_id"] = product_id
        p["current_price"] = round(live_price, 8)
        p["price"] = round(live_price, 8)
        p["market_value"] = round(market_value, 8)
        p["unrealized_pnl"] = round(unreal, 8)
        p["unrealized_pnl_pct"] = round(unreal_pct, 8)
        p["updated_at"] = now_iso()

        total_market += market_value
        total_unreal += unreal

    acct["position_value"] = round(total_market, 8)
    acct["unrealized_pnl"] = round(total_unreal, 8)
    acct["equity"] = round(cash + total_market, 8)
    acct["updated_by"] = "live_price_updater.py"
    acct["updated_at"] = now_iso()

    spot["positions"] = positions
    spot["updated_by"] = "live_price_updater.py"
    spot["updated_at"] = now_iso()
    spot["mode"] = "paper-live-market"

    save_json(SPOT_FILE, spot)
    save_json(ACCOUNT_FILE, acct)

    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"market={total_market:.2f} unreal={total_unreal:.2f} equity={cash + total_market:.2f}"
    )


def main() -> None:
    print("CSS live price updater running...")
    print(f"Spot file    : {SPOT_FILE}")
    print(f"Account file : {ACCOUNT_FILE}")
    print(f"Interval     : {INTERVAL}s")
    while True:
        try:
            update_prices()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"Update failed: {exc}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()