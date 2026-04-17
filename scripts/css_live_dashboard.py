from __future__ import annotations

import contextlib
import io
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

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

STATE_FILE = ARTIFACTS_DIR / "css_session_recovery.json"

# Force clean testing baseline.
# Set to False later only when we deliberately want session recovery again.
RESET_SESSION_ON_BOOT = True

if RESET_SESSION_ON_BOOT and STATE_FILE.exists():
    try:
        STATE_FILE.unlink()
        print("[RESET] Previous CSS recovery state deleted on boot.")
    except Exception as e:
        print(f"[RESET WARNING] Could not delete recovery state: {e}")

SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD",
]

FX_SYMBOLS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD",
    "USD_CAD", "NZD_USD", "EUR_GBP", "EUR_JPY", "GBP_JPY",
]

OPTION_SYMBOLS = ["AAPL-C", "SPY-C", "QQQ-C"]
FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]

CYCLE_SLEEP = 8

ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}

MODE_EXIT_PROFILE = {
    "SAFE": {"take_profit": 1.75, "stop_loss": -1.25, "max_age": 3},
    "CONSERVATIVE": {"take_profit": 2.25, "stop_loss": -1.75, "max_age": 4},
    "BALANCED": {"take_profit": 3.00, "stop_loss": -2.25, "max_age": 4},
    "AGGRESSIVE": {"take_profit": 4.00, "stop_loss": -3.00, "max_age": 5},
    "EXPANSION": {"take_profit": 5.00, "stop_loss": -3.75, "max_age": 6},
}

ASSET_DRIFT_PROFILE = {
    "CRYPTO": (-0.08, 0.16),
    "FX": (-0.03, 0.06),
    "OPTIONS": (-0.22, 0.34),
    "FUTURES": (-0.25, 0.38),
}

MAX_PAPER_OPEN_POSITIONS = 40
MAX_OPEN_PER_CYCLE = 4


def select_engine_mode() -> str:
    print("\n=== CSS ENGINE MODE SELECTOR ===")
    for k, v in ENGINE_MODES.items():
        print(f"{k}. {v}")

    choice = input("Enter choice (1-5) [default=3]: ").strip()
    return ENGINE_MODES.get(choice, "BALANCED")


def safe_load_runtime_asset(symbol: str) -> bool:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            load_runtime_asset(symbol)
        print(f"Fetched candles for {symbol}")
        return True
    except Exception as e:
        print(f"[FETCH FAIL] {symbol}: {str(e)[:80]}")
        return False


ENGINE_MODE = select_engine_mode()
print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")


class AdaptiveConcurrencyEnvelopeController:
    def __init__(self) -> None:
        self.current_limit = 300
        self.max_limit = 600
        self.min_limit = 250

    def evaluate_limit(
        self,
        open_positions: int,
        cluster_pct: float,
        unrealized_pnl: float,
    ) -> int:
        if (
            cluster_pct < 20.0
            and unrealized_pnl > 0.0
            and open_positions < self.current_limit * 0.75
        ):
            self.current_limit = min(self.current_limit + 50, self.max_limit)
        elif (
            cluster_pct > 35.0
            or unrealized_pnl < -50.0
            or open_positions > self.current_limit * 0.95
        ):
            self.current_limit = max(self.current_limit - 25, self.min_limit)

        return self.current_limit

    def can_add_position(self, open_positions: int) -> bool:
        return open_positions < self.current_limit


concurrency_controller = AdaptiveConcurrencyEnvelopeController()


class CapitalDeploymentGovernor:
    """
    Original dashboard-compatible capital governor.
    paper_mode stays True for safety.
    """

    def __init__(self) -> None:
        self.paper_mode = True
        self.live_capital_pool = 200.00
        self.max_capital_per_trade = 25.00
        self.max_live_positions = 5
        self.active_live_allocations: dict[str, float] = {}

    def available_capital(self) -> float:
        allocated = sum(self.active_live_allocations.values())
        return round(self.live_capital_pool - allocated, 4)

    def can_fund_trade(self, position_id: str) -> bool:
        if self.paper_mode:
            return False
        if position_id in self.active_live_allocations:
            return False
        if len(self.active_live_allocations) >= self.max_live_positions:
            return False
        if self.available_capital() < self.max_capital_per_trade:
            return False
        return True

    def allocate_trade(self, position_id: str) -> bool:
        if not self.can_fund_trade(position_id):
            return False
        self.active_live_allocations[position_id] = self.max_capital_per_trade
        return True

    def release_trade(self, position_id: str) -> None:
        if position_id in self.active_live_allocations:
            del self.active_live_allocations[position_id]

    def live_positions_count(self) -> int:
        return len(self.active_live_allocations)

    def funded_amount(self) -> float:
        return round(sum(self.active_live_allocations.values()), 4)

    def set_live_mode(self) -> None:
        self.paper_mode = False

    def set_paper_mode(self) -> None:
        self.paper_mode = True


capital_governor = CapitalDeploymentGovernor()


def map_oanda_env() -> None:
    if not os.getenv("OANDA_API_KEY"):
        if os.getenv("OANDA_PRACTICE_TOKEN"):
            os.environ["OANDA_API_KEY"] = os.getenv("OANDA_PRACTICE_TOKEN", "")
        elif os.getenv("OANDA_LIVE_TOKEN"):
            os.environ["OANDA_API_KEY"] = os.getenv("OANDA_LIVE_TOKEN", "")

    if not os.getenv("OANDA_ACCOUNT_ID"):
        if os.getenv("OANDA_PRACTICE_ACCOUNT_ID"):
            os.environ["OANDA_ACCOUNT_ID"] = os.getenv("OANDA_PRACTICE_ACCOUNT_ID", "")
        elif os.getenv("OANDA_LIVE_ACCOUNT_ID"):
            os.environ["OANDA_ACCOUNT_ID"] = os.getenv("OANDA_LIVE_ACCOUNT_ID", "")

    if not os.getenv("OANDA_BASE_URL"):
        env_mode = (os.getenv("OANDA_ENV") or "practice").strip().lower()
        if env_mode == "live":
            os.environ["OANDA_BASE_URL"] = "https://api-fxtrade.oanda.com"
        else:
            os.environ["OANDA_BASE_URL"] = "https://api-fxpractice.oanda.com"


map_oanda_env()
oanda = OandaAdapter()
class SessionRecoveryEngine:
    """
    Saves realized PnL and counters only.
    Open positions are deliberately not reloaded to prevent stale inflation.
    """

    def __init__(self) -> None:
        self.state_file = STATE_FILE

    def save_state(
        self,
        *,
        cycle: int,
        crypto_pnl: dict,
        fx_pnl: dict,
        options_pnl: dict,
        futures_pnl: dict,
        last_trade: str,
        position_counter: int,
    ) -> None:
        payload = {
            "cycle": cycle,
            "crypto_pnl": crypto_pnl,
            "fx_pnl": fx_pnl,
            "options_pnl": options_pnl,
            "futures_pnl": futures_pnl,
            "last_trade": last_trade,
            "position_counter": position_counter,
        }

        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def load_state(self):
        if RESET_SESSION_ON_BOOT:
            return None

        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


session_recovery = SessionRecoveryEngine()


class LockedProfitLedger:
    def __init__(self) -> None:
        self.forced_exit_profit_banked = 0.0
        self.priority_exits = 0
        self.recycled_slots = 0
        self.trail_stops_hit = 0
        self._booked: set[str] = set()

    def record_forced_exit(self, pid: str, amount: float) -> None:
        if pid in self._booked:
            return

        self._booked.add(pid)
        self.forced_exit_profit_banked += round(amount, 4)
        self.trail_stops_hit += 1

    def record_priority_exit(self) -> None:
        self.priority_exits += 1

    def record_recycled_slot(self) -> None:
        self.recycled_slots += 1


locked_profit_ledger = LockedProfitLedger()


class MomentumClusterAmplifier:
    def __init__(self) -> None:
        self.cluster_map = {
            "CRYPTO_CORE": ["BTC-USD", "ETH-USD", "SOL-USD"],
            "CRYPTO_ALT": ["XRP-USD", "ADA-USD", "DOGE-USD"],
            "FX_MAJOR": ["EUR_USD", "GBP_USD", "EUR_GBP"],
            "FX_YEN": ["USD_JPY", "EUR_JPY", "GBP_JPY"],
            "OPTIONS_INDEX": ["SPY-C", "QQQ-C", "AAPL-C"],
            "FUTURES_INDEX": ["ES", "NQ", "CL"],
        }

        self.cluster_strength: dict[str, float] = defaultdict(float)

    def record_cluster_win(self, symbol: str, pnl: float) -> None:
        if pnl <= 0:
            return

        for cname, members in self.cluster_map.items():
            if symbol in members:
                self.cluster_strength[cname] += pnl

    def top_cluster(self) -> str | None:
        if not self.cluster_strength:
            return None

        ranked = sorted(
            self.cluster_strength.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[0][0]


cluster_amplifier = MomentumClusterAmplifier()


class ClusterSaturationRiskGovernor:
    def __init__(self) -> None:
        self.cluster_slot_counts: dict[str, int] = defaultdict(int)
        self.total_slots_seen = 0

    def record_cluster_slot(self, cluster_name: str | None) -> None:
        if cluster_name:
            self.cluster_slot_counts[cluster_name] += 1
            self.total_slots_seen += 1

    def release_cluster_slot(self, cluster_name: str | None) -> None:
        if cluster_name and self.cluster_slot_counts[cluster_name] > 0:
            self.cluster_slot_counts[cluster_name] -= 1
            self.total_slots_seen = max(0, self.total_slots_seen - 1)

    def cluster_share(self, cluster_name: str | None) -> float:
        if not cluster_name or self.total_slots_seen == 0:
            return 0.0

        return self.cluster_slot_counts[cluster_name] / self.total_slots_seen


cluster_risk_governor = ClusterSaturationRiskGovernor()


class SmartDriftEngine:
    def generate_drift(self, pos: dict) -> float:
        lo, hi = ASSET_DRIFT_PROFILE.get(pos["asset_class"], (-0.05, 0.10))
        base = random.uniform(lo, hi)

        signal_bias = ((pos["signal_score"] - 10.0) / 10.0) * 0.04
        prob_bias = (pos["prob_positive"] - 0.5) * 0.08

        return round(base + signal_bias + prob_bias, 4)


smart_drift_engine = SmartDriftEngine()


class MarkToMarketEngine:
    def __init__(self) -> None:
        self.positions: list[dict] = []
        self.position_counter = 0

    def register_position(
        self,
        asset_class: str,
        symbol: str,
        signal_score: float,
        prob_positive: float,
    ) -> None:
        self.position_counter += 1
        pid = f"POS-{self.position_counter}"

        cluster_name = None
        for cname, members in cluster_amplifier.cluster_map.items():
            if symbol in members:
                cluster_name = cname
                break

        cluster_risk_governor.record_cluster_slot(cluster_name)
        funded_live = capital_governor.allocate_trade(pid)

        self.positions.append(
            {
                "position_id": pid,
                "asset_class": asset_class,
                "symbol": symbol,
                "cluster_name": cluster_name,
                "floating": 0.0,
                "forced_exit": False,
                "exit_reason": None,
                "age_cycles": 0,
                "signal_score": signal_score,
                "prob_positive": prob_positive,
                "live_funded": funded_live,
            }
        )

    def count_open_positions(self) -> int:
        return sum(1 for p in self.positions if not p["forced_exit"])

    def count_open_funded_positions(self) -> int:
        return sum(
            1
            for p in self.positions
            if not p["forced_exit"] and p.get("live_funded", False)
        )

    def floating_by_asset(self, funded_only: bool = False) -> dict[str, float]:
        by_asset = {
            "CRYPTO": 0.0,
            "FX": 0.0,
            "OPTIONS": 0.0,
            "FUTURES": 0.0,
        }

        for pos in self.positions:
            if pos["forced_exit"]:
                continue

            if funded_only and not pos.get("live_funded", False):
                continue

            by_asset[pos["asset_class"]] += pos["floating"]

        return by_asset


mtm_engine = MarkToMarketEngine()

crypto_pnl = {s: 0.0 for s in SYMBOLS}
fx_pnl = {s: 0.0 for s in FX_SYMBOLS}
options_pnl = {s: 0.0 for s in OPTION_SYMBOLS}
futures_pnl = {s: 0.0 for s in FUTURES_SYMBOLS}

last_trade = "NONE"
cycle = 0


saved_state = session_recovery.load_state()
if saved_state:
    cycle = 0

    crypto_pnl.update(saved_state.get("crypto_pnl", {}))
    fx_pnl.update(saved_state.get("fx_pnl", {}))
    options_pnl.update(saved_state.get("options_pnl", {}))
    futures_pnl.update(saved_state.get("futures_pnl", {}))

    last_trade = saved_state.get("last_trade", "NONE")

    mtm_engine.position_counter = saved_state.get("position_counter", 0)

    print(
        "[RECOVERY] Realized PnL restored, stale open positions not reloaded. "
        "Cycle counter reset."
    )


def total_realized_pnl() -> float:
    return round(
        sum(crypto_pnl.values())
        + sum(fx_pnl.values())
        + sum(options_pnl.values())
        + sum(futures_pnl.values()),
        4,
    )


def pnl_dict_for_asset(asset_class: str) -> dict:
    if asset_class == "CRYPTO":
        return crypto_pnl

    if asset_class == "FX":
        return fx_pnl

    if asset_class == "OPTIONS":
        return options_pnl

    if asset_class == "FUTURES":
        return futures_pnl

    raise ValueError(f"Unsupported asset class: {asset_class}")


def book_position_exit(pos: dict, reason: str) -> None:
    global last_trade

    if pos["forced_exit"]:
        return

    realized = round(pos["floating"], 4)

    pos["forced_exit"] = True
    pos["exit_reason"] = reason

    cluster_risk_governor.release_cluster_slot(pos["cluster_name"])

    if pos.get("live_funded", False):
        capital_governor.release_trade(pos["position_id"])

    target_pnl = pnl_dict_for_asset(pos["asset_class"])
    target_pnl[pos["symbol"]] = round(
        target_pnl.get(pos["symbol"], 0.0) + realized,
        4,
    )

    cluster_amplifier.record_cluster_win(pos["symbol"], realized)

    if reason == "STOP":
        locked_profit_ledger.record_forced_exit(pos["position_id"], realized)
    elif reason == "TAKE_PROFIT":
        locked_profit_ledger.record_priority_exit()

    locked_profit_ledger.record_recycled_slot()

    last_trade = f"{pos['symbol']} EXIT {reason} {realized:+.4f}"
def print_oanda_broker_status() -> None:
    print("\n--- OANDA BROKER STATUS ---")

    resolved_key = bool(os.getenv("OANDA_API_KEY"))
    resolved_account = bool(os.getenv("OANDA_ACCOUNT_ID"))
    resolved_base = os.getenv("OANDA_BASE_URL", "")

    if not (resolved_key and resolved_account):
        print("OANDA CONNECTED: NO")
        print(f"OANDA KEY PRESENT: {'YES' if resolved_key else 'NO'}")
        print(f"OANDA ACCOUNT PRESENT: {'YES' if resolved_account else 'NO'}")
        print(f"OANDA BASE URL: {resolved_base or 'NOT SET'}")
        return

    try:
        summary = oanda.get_account_summary()

        if not summary.get("ok", False):
            print(
                f"OANDA CONNECTED: ERROR "
                f"status={summary.get('status')} "
                f"error={summary.get('error')}"
            )
            print(f"OANDA BASE URL: {resolved_base or 'NOT SET'}")
            return

        nav = oanda.extract_balance_nav(summary)

        print("OANDA CONNECTED: YES")
        print(f"BALANCE: {nav['balance']}")
        print(f"NAV: {nav['nav']}")
        print(f"OANDA BASE URL: {resolved_base}")

    except Exception as e:
        print(f"OANDA ERROR: {str(e)[:60]}")
        print(f"OANDA BASE URL: {resolved_base or 'NOT SET'}")


def select_four_candidates() -> list[tuple[str, str, float, float]]:
    """
    Exactly 4 candidates per cycle:
    1 crypto, 1 FX, 1 option, 1 futures.
    """

    return [
        ("CRYPTO", random.choice(SYMBOLS), 12.0, 0.68),
        ("FX", random.choice(FX_SYMBOLS), 11.5, 0.66),
        ("OPTIONS", random.choice(OPTION_SYMBOLS), 14.0, 0.71),
        ("FUTURES", random.choice(FUTURES_SYMBOLS), 13.0, 0.69),
    ]


while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    # ============================
    # MARK-TO-MARKET + EXIT BOOKING
    # ============================
    exit_profile = MODE_EXIT_PROFILE.get(
        ENGINE_MODE,
        MODE_EXIT_PROFILE["BALANCED"],
    )

    for pos in mtm_engine.positions:
        if pos["forced_exit"]:
            continue

        drift = smart_drift_engine.generate_drift(pos)
        pos["floating"] = round(pos["floating"] + drift, 4)
        pos["age_cycles"] += 1

        if pos["floating"] <= exit_profile["stop_loss"]:
            book_position_exit(pos, "STOP")

        elif pos["floating"] >= exit_profile["take_profit"]:
            book_position_exit(pos, "TAKE_PROFIT")

        elif pos["age_cycles"] >= exit_profile["max_age"]:
            book_position_exit(pos, "TIME_EXIT")

    # ============================
    # PnL SUMMARY
    # Paper mode: display all floating PnL so dashboard updates.
    # Live mode: display funded floating PnL only.
    # ============================
    if capital_governor.paper_mode:
        display_by_asset = mtm_engine.floating_by_asset(funded_only=False)
    else:
        display_by_asset = mtm_engine.floating_by_asset(funded_only=True)

    funded_by_asset = mtm_engine.floating_by_asset(funded_only=True)

    funded_open_positions = mtm_engine.count_open_funded_positions()
    total_unrealized = round(sum(display_by_asset.values()), 4)
    open_positions = mtm_engine.count_open_positions()

    # ============================
    # LIMIT + CLUSTER CONTROL
    # ============================
    top_cluster = cluster_amplifier.top_cluster()
    cluster_pct = (
        cluster_risk_governor.cluster_share(top_cluster) * 100
        if top_cluster
        else 0.0
    )

    dynamic_limit = concurrency_controller.evaluate_limit(
        open_positions,
        cluster_pct,
        total_unrealized,
    )

    total_realized = total_realized_pnl()

    # ============================
    # OUTPUT
    # ============================
    print_oanda_broker_status()

    print("\n--- LIVE EXECUTION SUMMARY ---")
    print(f"REALIZED PNL: {total_realized:+.4f}")
    print(f"UNREALIZED PNL: {total_unrealized:+.4f}")
    print(f"TOTAL EQUITY PNL: {total_realized + total_unrealized:+.4f}")

    print(
        f"CRYPTO REALIZED: {sum(crypto_pnl.values()):+.4f} | "
        f"FLOATING: {display_by_asset['CRYPTO']:+.4f}"
    )

    print(
        f"FX REALIZED: {sum(fx_pnl.values()):+.4f} | "
        f"FLOATING: {display_by_asset['FX']:+.4f}"
    )

    print(
        f"OPTIONS REALIZED: {sum(options_pnl.values()):+.4f} | "
        f"FLOATING: {display_by_asset['OPTIONS']:+.4f}"
    )

    print(
        f"FUTURES REALIZED: {sum(futures_pnl.values()):+.4f} | "
        f"FLOATING: {display_by_asset['FUTURES']:+.4f}"
    )

    print(f"OPEN POSITIONS: {open_positions}")
    print(f"ADAPTIVE POSITION LIMIT: {dynamic_limit}")
    print(f"LIVE FUNDED POSITIONS: {funded_open_positions}")

    print(
        f"FUNDED CAPITAL DEPLOYED: "
        f"${capital_governor.funded_amount():.2f}"
    )

    print(
        f"AVAILABLE LIVE CAPITAL: "
        f"${capital_governor.available_capital():.2f}"
    )

    print(f"ENGINE MODE: {ENGINE_MODE}")

    print(
        f"FORCED EXIT PROFITS: "
        f"{locked_profit_ledger.forced_exit_profit_banked:+.4f}"
    )

    print(
        f"CLUSTER SATURATION: "
        f"{top_cluster if top_cluster else 'NONE'} {cluster_pct:.1f}%"
    )

    print(f"LAST TRADE: {last_trade}")
    print("-" * 60)

    # ============================
    # SIGNAL GENERATION
    # Corrected:
    # - exactly 4 candidates per cycle
    # - opens positions only
    # - no immediate pnl booking
    # ============================
    if mtm_engine.count_open_positions() < MAX_PAPER_OPEN_POSITIONS:
        for asset_class, symbol, sig, prob in select_four_candidates():
            if not concurrency_controller.can_add_position(
                mtm_engine.count_open_positions()
            ):
                break

            if mtm_engine.count_open_positions() >= MAX_PAPER_OPEN_POSITIONS:
                break

            if asset_class == "CRYPTO":
                safe_load_runtime_asset(symbol)

            mtm_engine.register_position(
                asset_class,
                symbol,
                sig,
                prob,
            )

            last_trade = f"{symbol} OPENED"
            print(f"[{asset_class} EXECUTED] {symbol} opened")
    else:
        print("[SIGNAL GENERATION PAUSED] paper open-position cap reached")

    # ============================
    # SAVE STATE
    # ============================
    session_recovery.save_state(
        cycle=cycle,
        crypto_pnl=crypto_pnl,
        fx_pnl=fx_pnl,
        options_pnl=options_pnl,
        futures_pnl=futures_pnl,
        last_trade=last_trade,
        position_counter=mtm_engine.position_counter,
    )

    time.sleep(CYCLE_SLEEP)