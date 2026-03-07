import json
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SPOT_FILE = ROOT / "backend" / "state" / "spot_position.json"
ACCOUNT_FILE = ROOT / "backend" / "state" / "account_state.json"

COINBASE = "https://api.exchange.coinbase.com/products/{}/ticker"

START_CAPITAL = 200
INVESTED = 135
CASH = 65

ASSETS = [
    ("BTC-USD", 40),
    ("ETH-USD", 35),
    ("SOL-USD", 25),
    ("AVAX-USD", 20),
    ("LINK-USD", 15),
]


def price(sym):
    r = requests.get(COINBASE.format(sym), timeout=10)
    r.raise_for_status()
    return float(r.json()["price"])


def load(p):
    return json.loads(p.read_text())


def save(p, d):
    p.write_text(json.dumps(d, indent=2))


spot = {"positions": []}

total = 0

for sym, alloc in ASSETS:

    px = price(sym)
    qty = alloc / px
    value = qty * px

    spot["positions"].append(
        {
            "asset": sym,
            "symbol": sym,
            "product_id": sym,
            "quantity": qty,
            "entry_price": px,
            "price": px,
            "current_price": px,
            "market_value": value,
            "unrealized_pnl": 0,
            "unrealized_pnl_pct": 0,
        }
    )

    total += value


acct = {
    "cash": CASH,
    "position_value": total,
    "equity": CASH + total,
    "unrealized_pnl": 0,
}

save(SPOT_FILE, spot)
save(ACCOUNT_FILE, acct)

print("Portfolio rebuilt at live prices.")
print("Equity:", CASH + total)