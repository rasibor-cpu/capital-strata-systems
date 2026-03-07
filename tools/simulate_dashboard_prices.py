import json
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SPOT_FILE = ROOT / "backend" / "state" / "spot_position.json"
ACCOUNT_FILE = ROOT / "backend" / "state" / "account_state.json"

INTERVAL = 10


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def update_prices():
    spot = load_json(SPOT_FILE)
    acct = load_json(ACCOUNT_FILE)

    positions = spot.get("positions", [])
    if not isinstance(positions, list):
        positions = []

    total_market = 0.0
    total_unreal = 0.0

    for p in positions:
        current_price = float(p.get("current_price") or p.get("price") or 0.0)
        entry_price = float(p.get("entry_price") or current_price or 0.0)
        qty = float(p.get("quantity") or p.get("qty") or 0.0)

        if current_price <= 0 or qty <= 0:
            continue

        # Bigger move so it is visible on the dashboard
        move = random.uniform(-0.05, 0.05)
        new_price = round(current_price * (1 + move), 8)

        market_value = round(qty * new_price, 8)
        unreal = round((new_price - entry_price) * qty, 8)
        unreal_pct = round(((new_price - entry_price) / entry_price) * 100.0, 8) if entry_price > 0 else 0.0

        p["current_price"] = new_price
        p["price"] = new_price
        p["market_value"] = market_value
        p["unrealized_pnl"] = unreal
        p["unrealized_pnl_pct"] = unreal_pct

        total_market += market_value
        total_unreal += unreal

    cash = float(
        acct.get("cash")
        or acct.get("cash_usd")
        or acct.get("available_cash")
        or 0.0
    )

    acct["position_value"] = round(total_market, 8)
    acct["unrealized_pnl"] = round(total_unreal, 8)
    acct["equity"] = round(cash + total_market, 8)
    acct["updated_by"] = "simulate_dashboard_prices.py"
    acct["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    spot["positions"] = positions
    spot["updated_by"] = "simulate_dashboard_prices.py"
    spot["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    save_json(SPOT_FILE, spot)
    save_json(ACCOUNT_FILE, acct)

    print(
        f"Updated | market={total_market:.2f} | unreal={total_unreal:.2f} | equity={cash + total_market:.2f}"
    )


def main():
    print("CSS dashboard simulator running...")
    print(f"Spot file    : {SPOT_FILE}")
    print(f"Account file : {ACCOUNT_FILE}")
    while True:
        update_prices()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()