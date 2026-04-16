from __future__ import annotations
import sys, time, json, random, os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.app.brokers.oanda_adapter import OandaAdapter

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

STATE_FILE = ARTIFACTS_DIR / "css_session_recovery.json"

SYMBOLS = ["BTC-USD","ETH-USD","SOL-USD","XRP-USD"]
FX_SYMBOLS = ["EUR_USD","GBP_USD"]

CYCLE_SLEEP = 8

ENGINE_MODES = {
    "1":"SAFE","2":"CONSERVATIVE","3":"BALANCED",
    "4":"AGGRESSIVE","5":"EXPANSION"
}

def select_engine_mode():
    print("\n=== CSS ENGINE MODE SELECTOR ===")
    for k,v in ENGINE_MODES.items():
        print(f"{k}. {v}")
    return ENGINE_MODES.get(input("Enter choice (1-5) [default=3]: ").strip(),"BALANCED")

ENGINE_MODE = select_engine_mode()
print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")
class CapitalDeploymentGovernor:
    def __init__(self):
        self.paper_mode = True
        self.live_capital_pool = 200.0
        self.max_positions = 5
        self.alloc = {}

    def available(self):
        return round(self.live_capital_pool - sum(self.alloc.values()),2)

    def allocate(self, pid):
        if self.paper_mode:
            return False
        if len(self.alloc) >= self.max_positions:
            return False
        self.alloc[pid] = 25.0
        return True

capital_governor = CapitalDeploymentGovernor()


# ===== OANDA ENV FIX =====
if not os.getenv("OANDA_API_KEY"):
    if os.getenv("OANDA_PRACTICE_TOKEN"):
        os.environ["OANDA_API_KEY"] = os.getenv("OANDA_PRACTICE_TOKEN")

if not os.getenv("OANDA_ACCOUNT_ID"):
    if os.getenv("OANDA_PRACTICE_ACCOUNT_ID"):
        os.environ["OANDA_ACCOUNT_ID"] = os.getenv("OANDA_PRACTICE_ACCOUNT_ID")

if not os.getenv("OANDA_BASE_URL"):
    os.environ["OANDA_BASE_URL"] = "https://api-fxpractice.oanda.com"

oanda = OandaAdapter()


class Engine:
    def __init__(self):
        self.positions = []
        self.counter = 0

    def add(self, asset, symbol):
        self.counter += 1
        pid = f"P{self.counter}"
        funded = capital_governor.allocate(pid)

        self.positions.append({
            "id": pid,
            "asset": asset,
            "symbol": symbol,
            "floating": 0.0,
            "funded": funded,
            "closed": False
        })

    def open(self):
        return [p for p in self.positions if not p.get("closed",False)]

    def funded(self):
        return [p for p in self.open() if p.get("funded",False)]

engine = Engine()

crypto_pnl = {s:0.0 for s in SYMBOLS}
fx_pnl = {s:0.0 for s in FX_SYMBOLS}

cycle = 0

# ===== RECOVERY FIX =====
if STATE_FILE.exists():
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)

        # ⚠️ DO NOT restore positions to avoid fake first-cycle inflation
        crypto_pnl.update(data.get("crypto_pnl",{}))
        fx_pnl.update(data.get("fx_pnl",{}))

        print("[RECOVERY] PnL restored, positions reset")

    except:
        print("[RECOVERY ERROR]")
def print_oanda():
    print("\n--- OANDA BROKER STATUS ---")

    if not (os.getenv("OANDA_API_KEY") and os.getenv("OANDA_ACCOUNT_ID")):
        print("OANDA CONNECTED: NO")
        return

    try:
        s = oanda.get_account_summary()
        nav = oanda.extract_balance_nav(s)

        print("OANDA CONNECTED: YES")
        print(f"BALANCE: {nav['balance']}")
        print(f"NAV: {nav['nav']}")
    except Exception as e:
        print(f"OANDA ERROR: {str(e)[:50]}")


while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    # simulate MTM
    for p in engine.open():
        p["floating"] += random.uniform(-2,3)

    funded = engine.funded()

    # ===== FIXED PnL =====
    unrealized = sum(p["floating"] for p in funded) if funded else 0.0
    realized = sum(crypto_pnl.values()) + sum(fx_pnl.values())

    print_oanda()

    print("\n--- LIVE EXECUTION SUMMARY ---")
    print(f"REALIZED PNL: {realized:+.4f}")
    print(f"UNREALIZED PNL: {unrealized:+.4f}")
    print(f"TOTAL EQUITY: {realized+unrealized:+.4f}")
    print(f"OPEN POSITIONS: {len(engine.open())}")
    print(f"LIVE FUNDED POSITIONS: {len(funded)}")
    print(f"AVAILABLE CAPITAL: ${capital_governor.available():.2f}")
    print(f"ENGINE MODE: {ENGINE_MODE}")

    # simulate trading
    for s in SYMBOLS:
        engine.add("CRYPTO",s)
        pnl = random.uniform(-5,10)
        crypto_pnl[s]+=pnl

    for s in FX_SYMBOLS:
        engine.add("FX",s)
        pnl = random.uniform(-3,6)
        fx_pnl[s]+=pnl

    # save (without positions to prevent inflation)
    with open(STATE_FILE,"w") as f:
        json.dump({
            "crypto_pnl":crypto_pnl,
            "fx_pnl":fx_pnl
        },f)

    time.sleep(CYCLE_SLEEP)