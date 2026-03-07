import json
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SPOT_FILE = ROOT / "backend" / "state" / "spot_position.json"
ACCOUNT_FILE = ROOT / "backend" / "state" / "account_state.json"

COINBASE = "https://api.exchange.coinbase.com/products/{}/ticker"


def price(product):
    r = requests.get(COINBASE.format(product), timeout=10)
    r.raise_for_status()
    return float(r.json()["price"])


def load(p):
    return json.loads(p.read_text())


def save(p, d):
    p.write_text(json.dumps(d, indent=2))


spot = load(SPOT_FILE)
acct = load(ACCOUNT_FILE)

positions = spot.get("positions", [])

total = 0

for p in positions:

    sym = p.get("asset") or p.get("symbol")
    px = price(sym)

    qty = float(p.get("qty") or p.get("quantity"))

    p["entry_price"] = px
    p["price"] = px
    p["current_price"] = px
    p["market_value"] = qty * px
    p["unrealized_pnl"] = 0
    p["unrealized_pnl_pct"] = 0

    total += qty * px


cash = float(acct.get("cash") or acct.get("cash_usd") or 0)

acct["position_value"] = total
acct["unrealized_pnl"] = 0
acct["equity"] = cash + total

save(SPOT_FILE, spot)
save(ACCOUNT_FILE, acct)

print("Positions reset to live market prices.")
print("Portfolio equity:", cash + total)