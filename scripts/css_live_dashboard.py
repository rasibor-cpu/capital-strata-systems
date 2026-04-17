from __future__ import annotations

import json
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.app.brokers.oanda_adapter import OandaAdapter


# =========================================================
# CONFIG
# =========================================================
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

STATE_FILE = ARTIFACTS_DIR / "css_session_recovery.json"

CRYPTO_SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
    "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD"
]
FX_SYMBOLS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF",
    "AUD_USD", "USD_CAD", "NZD_USD", "EUR_GBP"
]
OPTION_SYMBOLS = ["SPY-C", "QQQ-C", "AAPL-C"]
FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]

ASSET_MAP = {
    "CRYPTO": CRYPTO_SYMBOLS,
    "FX": FX_SYMBOLS,
    "OPTIONS": OPTION_SYMBOLS,
    "FUTURES": FUTURES_SYMBOLS,
}

PRICE_DEFAULTS = {
    "BTC-USD": 65000.0,
    "ETH-USD": 3200.0,
    "SOL-USD": 145.0,
    "XRP-USD": 0.62,
    "ADA-USD": 0.58,
    "DOGE-USD": 0.17,
    "AVAX-USD": 38.0,
    "LINK-USD": 18.5,
    "EUR_USD": 1.0850,
    "GBP_USD": 1.2720,
    "USD_JPY": 151.20,
    "USD_CHF": 0.9040,
    "AUD_USD": 0.6640,
    "USD_CAD": 1.3640,
    "NZD_USD": 0.6070,
    "EUR_GBP": 0.8520,
    "SPY-C": 5.40,
    "QQQ-C": 6.10,
    "AAPL-C": 4.85,
    "ES": 5250.0,
    "NQ": 18350.0,
    "CL": 79.20,
    "GC": 2380.0,
}

POINT_VALUE = {
    "CRYPTO": 1.0,
    "FX": 10.0,
    "OPTIONS": 100.0,
    "FUTURES": 50.0,
}

QTY_BY_ASSET = {
    "CRYPTO": 0.0015,
    "FX": 1.0,
    "OPTIONS": 1.0,
    "FUTURES": 1.0,
}

MOVE_BPS = {
    "CRYPTO": 140,
    "FX": 22,
    "OPTIONS": 260,
    "FUTURES": 45,
}

OPEN_PER_CYCLE = {
    "CRYPTO": 1,
    "FX": 1,
    "OPTIONS": 1,
    "FUTURES": 1,
}

MAX_OPEN_POSITIONS = 12
MAX_FUNDED_POSITIONS = 5
ALLOC_PER_POSITION = 25.0
INITIAL_CAPITAL = 200.0
CYCLE_SLEEP = 8
MAX_POSITION_AGE = 4

ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}

MODE_PROFILE = {
    "SAFE": {"close_abs": 6.0, "max_age": 3},
    "CONSERVATIVE": {"close_abs": 7.5, "max_age": 4},
    "BALANCED": {"close_abs": 10.0, "max_age": 4},
    "AGGRESSIVE": {"close_abs": 13.0, "max_age": 5},
    "EXPANSION": {"close_abs": 15.0, "max_age": 6},
}


# =========================================================
# BOOT
# =========================================================
def select_engine_mode() -> str:
    print("\n=== CSS ENGINE MODE SELECTOR ===")
    for k, v in ENGINE_MODES.items():
        print(f"{k}. {v}")
    choice = input("Enter choice (1-5) [default=3]: ").strip() or "3"
    return ENGINE_MODES.get(choice, "BALANCED")


ENGINE_MODE = select_engine_mode()
print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")


def safe_load_runtime_asset(symbol: str) -> bool:
    try:
        load_runtime_asset(symbol)
        return True
    except Exception:
        return False


# =========================================================
# OANDA
# =========================================================
if not os.getenv("OANDA_API_KEY") and os.getenv("OANDA_PRACTICE_TOKEN"):
    os.environ["OANDA_API_KEY"] = os.getenv("OANDA_PRACTICE_TOKEN")

if not os.getenv("OANDA_ACCOUNT_ID") and os.getenv("OANDA_PRACTICE_ACCOUNT_ID"):
    os.environ["OANDA_ACCOUNT_ID"] = os.getenv("OANDA_PRACTICE_ACCOUNT_ID")

if not os.getenv("OANDA_BASE_URL"):
    os.environ["OANDA_BASE_URL"] = "https://api-fxpractice.oanda.com"

oanda = OandaAdapter()


# =========================================================
# CAPITAL
# =========================================================
class CapitalGovernor:
    def __init__(self, capital: float = INITIAL_CAPITAL, alloc: dict | None = None):
        self.capital = float(capital)
        self.alloc = dict(alloc or {})
        self.max_positions = MAX_FUNDED_POSITIONS

    def allocate(self, pid: str, amount: float = ALLOC_PER_POSITION) -> bool:
        if len(self.alloc) >= self.max_positions:
            return False
        if self.available() < amount:
            return False
        self.alloc[pid] = float(amount)
        return True

    def release(self, pid: str) -> None:
        self.alloc.pop(pid, None)

    def available(self) -> float:
        return round(self.capital - sum(self.alloc.values()), 2)

    def funded_count(self) -> int:
        return len(self.alloc)# =========================================================
# ENGINE
# =========================================================
class Engine:
    def __init__(self):
        self.positions: list[dict] = []
        self.counter = 0
        self.closed_log: list[dict] = []
        self.candidate_log: list[str] = []
        self.last_live_note = "NONE"

    def next_id(self) -> str:
        self.counter += 1
        return f"P{self.counter}"

    def open_positions(self) -> list[dict]:
        return [p for p in self.positions if p["status"] == "OPEN"]

    def funded_positions(self) -> list[dict]:
        return [p for p in self.open_positions() if p["funded"]]

    def recent_closed(self, n: int = 8) -> list[dict]:
        return self.closed_log[-n:]

    def reset_cycle_log(self) -> None:
        self.candidate_log = []


def infer_entry_price(symbol: str) -> float:
    return float(PRICE_DEFAULTS.get(symbol, 100.0))


def calc_floating(position: dict) -> float:
    direction_mult = 1.0 if position["side"] == "BUY" else -1.0
    px_diff = (position["current_price"] - position["entry_price"]) * direction_mult
    return round(px_diff * position["qty"] * position["point_value"], 4)


def simulate_next_price(position: dict) -> float:
    bps = MOVE_BPS.get(position["asset"], 40)
    shock = random.uniform(-bps, bps) / 10000.0
    next_px = position["current_price"] * (1.0 + shock)
    return max(0.0001, round(next_px, 6))


def should_close(position: dict) -> bool:
    profile = MODE_PROFILE[ENGINE_MODE]
    close_abs = profile["close_abs"]
    max_age = profile["max_age"]

    if abs(position["floating"]) >= close_abs:
        return True
    if position["age"] >= max_age:
        return True
    return False


def make_position(pid: str, asset: str, symbol: str, funded: bool) -> dict:
    entry_price = infer_entry_price(symbol)
    return {
        "id": pid,
        "asset": asset,
        "symbol": symbol,
        "status": "OPEN",
        "side": "BUY",
        "entry_price": entry_price,
        "current_price": entry_price,
        "qty": QTY_BY_ASSET[asset],
        "point_value": POINT_VALUE[asset],
        "floating": 0.0,
        "realized": 0.0,
        "funded": funded,
        "allocated": ALLOC_PER_POSITION if funded else 0.0,
        "age": 0,
        "opened_at": datetime.now().isoformat(timespec="seconds"),
        "closed_at": None,
    }


def save_state(
    cycle: int,
    capital: CapitalGovernor,
    pnl_by_class: dict,
    positions: list[dict],
    closed_log: list[dict],
) -> None:
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "cycle": cycle,
        "engine_mode": ENGINE_MODE,
        "capital": capital.capital,
        "alloc": capital.alloc,
        "pnl_by_class": pnl_by_class,
        "positions": positions,
        "closed_log": closed_log[-20:],
    }
    try:
        STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[STATE SAVE WARNING] {e}")


def load_state() -> dict | None:
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[STATE LOAD WARNING] {e}")
        return None


restored = load_state()

if restored:
    capital = CapitalGovernor(
        capital=restored.get("capital", INITIAL_CAPITAL),
        alloc=restored.get("alloc", {}),
    )
    pnl_by_class = restored.get(
        "pnl_by_class",
        {"CRYPTO": 0.0, "FX": 0.0, "OPTIONS": 0.0, "FUTURES": 0.0},
    )
    engine = Engine()
    engine.positions = restored.get("positions", [])
    engine.closed_log = restored.get("closed_log", [])
    engine.counter = len(engine.positions)
    cycle = int(restored.get("cycle", 0))
    print(f"[STATE RESTORED] cycle={cycle} capital={capital.capital:.4f}")
else:
    capital = CapitalGovernor()
    pnl_by_class = {"CRYPTO": 0.0, "FX": 0.0, "OPTIONS": 0.0, "FUTURES": 0.0}
    engine = Engine()
    cycle = 0


# =========================================================
# CYCLE LOGIC
# =========================================================
def update_positions() -> dict:
    cycle_closed = {"CRYPTO": 0.0, "FX": 0.0, "OPTIONS": 0.0, "FUTURES": 0.0}

    for p in engine.open_positions():
        p["age"] += 1
        p["current_price"] = simulate_next_price(p)
        p["floating"] = calc_floating(p)

        if should_close(p):
            p["status"] = "CLOSED"
            p["closed_at"] = datetime.now().isoformat(timespec="seconds")
            p["realized"] = round(p["floating"], 4)

            if p["funded"]:
                capital.capital = round(capital.capital + p["realized"], 4)
                capital.release(p["id"])

            pnl_by_class[p["asset"]] = round(pnl_by_class[p["asset"]] + p["realized"], 4)
            cycle_closed[p["asset"]] = round(cycle_closed[p["asset"]] + p["realized"], 4)

            engine.closed_log.append(
                {
                    "id": p["id"],
                    "asset": p["asset"],
                    "symbol": p["symbol"],
                    "funded": p["funded"],
                    "realized": p["realized"],
                    "age": p["age"],
                    "closed_at": p["closed_at"],
                }
            )
            p["floating"] = 0.0

    return cycle_closed


def generate_candidates() -> None:
    engine.reset_cycle_log()

    if len(engine.open_positions()) >= MAX_OPEN_POSITIONS:
        engine.candidate_log.append("OPEN POSITION CAP REACHED - no new candidates opened")
        return

    for asset, count in OPEN_PER_CYCLE.items():
        for _ in range(count):
            if len(engine.open_positions()) >= MAX_OPEN_POSITIONS:
                engine.candidate_log.append("OPEN POSITION CAP REACHED MID-CYCLE")
                return

            symbol = random.choice(ASSET_MAP[asset])
            safe_load_runtime_asset(symbol)

            pid = engine.next_id()
            funded = capital.allocate(pid)
            if not funded:
                position = make_position(pid, asset, symbol, funded=False)
                engine.positions.append(position)
                engine.candidate_log.append(f"{asset:<7} {symbol:<10} -> SIM (CAP_LIMIT)")
                engine.last_live_note = f"{symbol} CAP_LIMIT"
            else:
                position = make_position(pid, asset, symbol, funded=True)
                engine.positions.append(position)
                engine.candidate_log.append(f"{asset:<7} {symbol:<10} -> FUNDED")
                engine.last_live_note = f"{symbol} FUNDED"


def get_broker_status() -> tuple[str, str, str]:
    try:
        summary = oanda.get_account_summary()
        nav = oanda.extract_balance_nav(summary)
        balance = str(nav.get("balance", "N/A"))
        nav_v = str(nav.get("nav", "N/A"))
        return "YES", balance, nav_v
    except Exception:
        return "ERROR", "N/A", "N/A"


def fmt_money(v: float) -> str:
    return f"{v:+.4f}"


def fmt_plain(v: float) -> str:
    return f"{v:.4f}"
# =========================================================
# DASHBOARD RENDER
# =========================================================
def print_divider(width: int = 78) -> None:
    print("-" * width)


def print_cycle_header(cycle_no: int) -> None:
    print_divider()
    print(f"=== Cycle {cycle_no} | {datetime.now()} ===")
    print_divider()


def print_broker_panel() -> None:
    connected, balance, nav = get_broker_status()
    print("\n--- OANDA BROKER STATUS ---")
    print(f"OANDA CONNECTED: {connected}")
    print(f"BROKER BALANCE:  {balance}")
    print(f"BROKER NAV:      {nav}")


def print_live_panel() -> None:
    funded = engine.funded_positions()
    open_pos = engine.open_positions()

    live_unreal = round(sum(p["floating"] for p in funded), 4)
    sim_unreal = round(sum(p["floating"] for p in open_pos if not p["funded"]), 4)
    realized = round(sum(pnl_by_class.values()), 4)
    equity = round(capital.capital + live_unreal, 4)

    print("\n--- LIVE ACCOUNTING ---")
    print(f"REALIZED PNL:         {fmt_money(realized)}")
    print(f"LIVE UNREALIZED PNL:  {fmt_money(live_unreal)}")
    print(f"SIM UNREALIZED PNL:   {fmt_money(sim_unreal)}")
    print(f"TOTAL EQUITY:         {fmt_plain(equity)}")
    print(f"CAPITAL BASE:         {fmt_plain(capital.capital)}")
    print(f"OPEN POSITIONS:       {len(open_pos)}")
    print(f"LIVE FUNDED POSITIONS:{engine and ' ' or ''}{len(funded)}")
    print(f"AVAILABLE CAPITAL:    {capital.available():.2f}")
    print(f"ENGINE MODE:          {ENGINE_MODE}")
    print(f"LAST LIVE NOTE:       {engine.last_live_note}")


def print_asset_panel(cycle_closed: dict) -> None:
    print("\n--- BY ASSET CLASS ---")
    for asset in ["CRYPTO", "FX", "OPTIONS", "FUTURES"]:
        total = pnl_by_class.get(asset, 0.0)
        this_cycle = cycle_closed.get(asset, 0.0)
        print(
            f"{asset:<8} TOTAL {fmt_money(total):>12} | "
            f"CYCLE CLOSED {fmt_money(this_cycle):>12}"
        )


def print_open_positions_panel() -> None:
    print("\n--- OPEN POSITIONS DETAIL ---")
    open_pos = engine.open_positions()
    if not open_pos:
        print("No open positions")
        return

    print("ID     TYPE     SYMBOL      FND   AGE   ENTRY        CURR         FLOAT")
    print_divider()
    for p in open_pos[-10:]:
        funded_tag = "Y" if p["funded"] else "N"
        print(
            f"{p['id']:<6} "
            f"{p['asset']:<8} "
            f"{p['symbol']:<10} "
            f"{funded_tag:<5} "
            f"{p['age']:<5} "
            f"{p['entry_price']:<12.6f} "
            f"{p['current_price']:<12.6f} "
            f"{p['floating']:+.4f}"
        )


def print_recent_closed_panel() -> None:
    print("\n--- RECENT CLOSED POSITIONS ---")
    rows = engine.recent_closed(8)
    if not rows:
        print("No closed positions yet")
        return

    print("ID     TYPE     SYMBOL      FND   AGE   REALIZED      CLOSED_AT")
    print_divider()
    for r in rows:
        funded_tag = "Y" if r["funded"] else "N"
        print(
            f"{r['id']:<6} "
            f"{r['asset']:<8} "
            f"{r['symbol']:<10} "
            f"{funded_tag:<5} "
            f"{r['age']:<5} "
            f"{r['realized']:+10.4f}   "
            f"{r['closed_at']}"
        )


def print_candidate_panel() -> None:
    print("\n--- CANDIDATE / EXECUTION NOTES ---")
    if not engine.candidate_log:
        print("No candidate activity this cycle")
        return
    for note in engine.candidate_log[-8:]:
        print(note)


def print_cycle_stats_panel() -> None:
    open_pos = engine.open_positions()
    funded = engine.funded_positions()

    by_asset_open = defaultdict(int)
    by_asset_funded = defaultdict(int)

    for p in open_pos:
        by_asset_open[p["asset"]] += 1
        if p["funded"]:
            by_asset_funded[p["asset"]] += 1

    print("\n--- CYCLE STATS ---")
    print(
        f"OPEN MIX: CRYPTO {by_asset_open['CRYPTO']} | FX {by_asset_open['FX']} | "
        f"OPTIONS {by_asset_open['OPTIONS']} | FUTURES {by_asset_open['FUTURES']}"
    )
    print(
        f"FUNDED MIX: CRYPTO {by_asset_funded['CRYPTO']} | FX {by_asset_funded['FX']} | "
        f"OPTIONS {by_asset_funded['OPTIONS']} | FUTURES {by_asset_funded['FUTURES']}"
    )
    print(f"TOTAL CLOSED LOGGED: {len(engine.closed_log)}")
    print(f"FUNDED SLOTS USED:   {capital.funded_count()} / {MAX_FUNDED_POSITIONS}")


# =========================================================
# MAIN LOOP
# =========================================================
while True:
    cycle += 1

    cycle_closed = update_positions()
    generate_candidates()

    print_cycle_header(cycle)
    print_broker_panel()
    print_live_panel()
    print_asset_panel(cycle_closed)
    print_open_positions_panel()
    print_recent_closed_panel()
    print_candidate_panel()
    print_cycle_stats_panel()

    save_state(
        cycle=cycle,
        capital=capital,
        pnl_by_class=pnl_by_class,
        positions=engine.positions,
        closed_log=engine.closed_log,
    )

    time.sleep(CYCLE_SLEEP)