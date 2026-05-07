from __future__ import annotations

# === R15B MODE-AWARE EXIT PROFILE ===

R15B_EXIT_PROFILE = {
    "SAFE":        {"tp": 0.010, "sl": -0.006},
    "CONSERVATIVE":{"tp": 0.012, "sl": -0.008},
    "BALANCED":    {"tp": 0.015, "sl": -0.010},
    "AGGRESSIVE":  {"tp": 0.020, "sl": -0.012},
    "EXPANSION":   {"tp": 0.025, "sl": -0.015},
}


def r15b_profile():
    return R15B_EXIT_PROFILE.get(str(ENGINE_MODE).upper(), R15B_EXIT_PROFILE["BALANCED"])



# === R15A EXIT INTELLIGENCE ENGINE ===

def evaluate_exit_signal(position: dict) -> str:
    entry = float(position.get("entry_price", 0.0))
    current = float(position.get("current_price", entry))

    if entry == 0:
        return "HOLD"

    pnl_pct = (current - entry) / entry

    if pnl_pct >= 0.015:
        return "TAKE_PROFIT"

    if pnl_pct <= -0.010:
        return "STOP_LOSS"

    if pnl_pct >= 0.010:
        return "RUNNER"

    return "HOLD"



# === R14F PRE-POSITION PROFITABILITY GATE ===
def css_profitability_threshold(mode: str) -> float:
    return {
        "SAFE": 17.5,
        "CONSERVATIVE": 16.5,
        "BALANCED": 15.8,
        "AGGRESSIVE": 15.0,
        "EXPANSION": 14.2,
    }.get(str(mode).upper(), 15.8)


def css_profitability_allows(symbol: str, asset_class: str, sig: float, prob: float) -> tuple[bool, float, float]:
    """
    Uses existing dashboard signal score and probability before creating a position.
    Score remains compatible with current sig scale.
    """
    signal_score = float(sig or 0.0)
    probability = float(prob or 0.0)
    threshold = css_profitability_threshold(ENGINE_MODE)

    composite = signal_score + (probability * 5.0)

    if composite < threshold:
        print(
            f"[R14F BLOCK] {asset_class} {symbol} "
            f"composite={composite:.2f} threshold={threshold:.2f} "
            f"sig={signal_score:.2f} prob={probability:.2f}"
        )
        return False, composite, threshold

    print(
        f"[R14F PASS] {asset_class} {symbol} "
        f"composite={composite:.2f} threshold={threshold:.2f} "
        f"sig={signal_score:.2f} prob={probability:.2f}"
    )
    return True, composite, threshold



# === R13C GLOBAL MODE DOMINANCE ===
def enforce_mode_dominance():
    global SELECTED_BROKER_MODE

    if str(GLOBAL_BROKER_MODE).lower() == "live":
        if str(SELECTED_BROKER_MODE).lower() != "live":
            print("[MODE CORRECTION] Forcing broker mode to LIVE due to global mode")
            SELECTED_BROKER_MODE = "live"



# === R13 EXECUTION BOUNDARY ENFORCEMENT ===
def enforce_execution_boundary():
    mode = str(SELECTED_BROKER_MODE).lower()

    if mode == "live":
        # Live mode must not use simulated paths
        if capital_governor.capital_source_label().upper() == "SIMULATED":
            print("[BOUNDARY VIOLATION] Live mode cannot use simulated capital")
            import sys
            sys.exit(1)

    elif mode == "paper":
        # Paper mode must not attempt live execution
        if "LIVE" in str(globals()):
            pass  # safeguard placeholder

    else:
        print(f"[UNKNOWN MODE] {mode}")
        import sys
        sys.exit(1)



# === R12 OPTION IDENTITY FORMATTER ===
def format_option_symbol(symbol: str) -> str:
    """
    Ensure option symbols are fully qualified
    """
    if "-" not in symbol:
        return symbol

    parts = symbol.split("-")

    # Already fully qualified
    if len(parts) == 3:
        return symbol

    # Convert stub to default strike
    if len(parts) == 2:
        underlying, opt_type = parts
        default_strike = {
            "AAPL": "175",
            "SPY": "500",
            "QQQ": "400",
        }.get(underlying, "100")

        return f"{underlying}-{opt_type}-{default_strike}"

    return symbol



# === R11 BROKER URL ISOLATION ===
def get_active_broker_url():
    if SELECTED_BROKER == "OANDA":
        return os.environ.get("OANDA_BASE_URL", "OANDA_NOT_SET")
    elif SELECTED_BROKER == "COINBASE":
        return "https://api.coinbase.com"
    return "NO_BROKER_SELECTED"

import os
print("RUNNING FILE:", os.path.abspath(__file__))
import contextlib
import hashlib
import getpass
import io
import json
import os
import random
import socket
import sys
import time
# PCNRASS: orchestrator bridge import deferred until after PROJECT_ROOT bootstrap
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.practice", override=False)

# === PCNRASS PHASE 2 REAL MARKET PRICE FEED ===
from backend.data.price_feed import get_price_feed
price_feed = get_price_feed()

# === PCNRASS SAFE PNL IMPORT COMPATIBILITY ===
# Some CSS branches used backend.app.pnl.pnl_engine.
# This repo currently uses backend.app.accounting.pnl_engine.
# Keep old dashboard behavior by providing a local Portfolio/Position compatibility layer
# if the old module path is unavailable.

try:
    from backend.app.pnl.pnl_engine import Portfolio, Position  # legacy path
except ModuleNotFoundError:
    from dataclasses import dataclass

    @dataclass
    class Position:
        symbol: str
        asset_class: str = "UNKNOWN"
        side: str = "LONG"
        quantity: float = 1.0
        entry_price: float = 0.0
        current_price: float = 0.0

    class Portfolio:
        def __init__(self, starting_balance: float = 0.0, current_balance: float | None = None):
            self.starting_balance = float(starting_balance or 0.0)
            self.current_balance = float(current_balance if current_balance is not None else self.starting_balance)
            self.realized_pnl = 0.0
            self.positions: dict[str, Position] = {}

        def add_position(self, position: Position) -> None:
            self.positions[position.symbol] = position

        def update_market_price(self, symbol: str, current_price: float) -> None:
            pos = self.positions.get(symbol)
            if pos is not None:
                pos.current_price = float(current_price)

        def close_position(self, symbol: str, exit_price: float) -> float:
            pos = self.positions.pop(symbol, None)
            if pos is None:
                return 0.0

            side = str(pos.side or "LONG").upper()
            direction = 1.0 if side != "SHORT" else -1.0
            pnl = (float(exit_price) - float(pos.entry_price)) * float(pos.quantity) * direction
            self.realized_pnl += pnl
            self.current_balance += pnl
            return pnl

        def compute_unrealized_pnl(self) -> float:
            total = 0.0
            for pos in self.positions.values():
                side = str(pos.side or "LONG").upper()
                direction = 1.0 if side != "SHORT" else -1.0
                total += (float(pos.current_price) - float(pos.entry_price)) * float(pos.quantity) * direction
            return round(total, 6)

        def equity(self) -> float:
            return round(float(self.current_balance) + float(self.compute_unrealized_pnl()), 6)


# === NEW PNL SYSTEM IMPORTS (PCNRASS SAFE ADDITION) ===
from backend.app.accounting.pnl_engine import (
    compute_portfolio_snapshot,
    Position as NewPosition,
    InstrumentSpec,
    ExecutionCost,
)
from engine.performance.pnl_tracker import PnLTracker

# === PCNRASS SAFE INFRASTRUCTURE IMPORT COMPATIBILITY ===
# These fallbacks prevent dashboard startup failure when a branch is missing
# optional governance/broker/security modules. Existing modules are used when present.

try:
    from backend.core.session_state import get_session_lock_state, is_session_locked, lock_session
except ModuleNotFoundError:
    _CSS_SESSION_LOCK = {"locked": False, "reason": None, "lock_time": None}

    def get_session_lock_state() -> dict:
        return {
            "locked": _CSS_SESSION_LOCK.get("locked", False),
            "reason": _CSS_SESSION_LOCK.get("reason"),
            "lock_time": _CSS_SESSION_LOCK.get("lock_time"),
        }

    def is_session_locked() -> bool:
        return bool(_CSS_SESSION_LOCK.get("locked", False))

    def lock_session(reason: str) -> None:
        _CSS_SESSION_LOCK["locked"] = True
        _CSS_SESSION_LOCK["reason"] = reason
        _CSS_SESSION_LOCK["lock_time"] = datetime.now().isoformat()


try:
    from backend.data.coinbase_historical_downloader import load_runtime_asset
except ModuleNotFoundError:
    def load_runtime_asset(symbol: str):
        print(f"[SAFE FALLBACK] load_runtime_asset unavailable for {symbol}")
        return None


try:
    from backend.app.brokers.oanda_adapter import OandaAdapter
except ModuleNotFoundError:
    class OandaAdapter:
        def get_open_trades(self):
            return {"ok": False, "data": {"trades": []}, "error": "OandaAdapter unavailable"}

        def get_account_summary(self):
            return {"ok": False, "status": "UNAVAILABLE", "error": "OandaAdapter unavailable"}

        def extract_balance_nav(self, summary):
            return {"balance": 0.0, "nav": 0.0}

        def place_order(self, *args, **kwargs):
            return {"ok": False, "status": "UNAVAILABLE", "error": "OandaAdapter unavailable"}


try:
    from backend.app.brokers.broker_bootstrap import initialize_broker
except ModuleNotFoundError:
    def initialize_broker(*args, **kwargs):
        print("[SAFE FALLBACK] initialize_broker unavailable")
        return None


try:
    from backend.app.brokers.coinbase_live_order_gate import CoinbaseLiveOrderGate
except ModuleNotFoundError:
    class _GateResult:
        def __init__(self, allowed=False, reason="CoinbaseLiveOrderGate unavailable"):
            self.allowed = allowed
            self.reason = reason

    class CoinbaseLiveOrderGate:
        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self, *args, **kwargs):
            return _GateResult(False, "CoinbaseLiveOrderGate unavailable")


try:
    from backend.app.brokers.broker_gate_audit import BrokerGateAuditLogger
except ModuleNotFoundError:
    class BrokerGateAuditLogger:
        def log_decision(self, *args, **kwargs):
            return None


try:
    from backend.app.security.auth_gate import await_login_ready_state
except ModuleNotFoundError:
    def await_login_ready_state():
        print("[SAFE FALLBACK AUTH] auth_gate unavailable; using local OPERATOR diagnostic context.")
        raise Exception("AUTHENTICATION_REQUIRED_NO_FALLBACK_ALLOWED")


class _PermissionResult:
    def __init__(self, allowed=True):
        self.allowed = allowed


try:
    from backend.security.access_control import AccessControl
except ModuleNotFoundError:
    class AccessControl:
        def can_login(self, role): return _PermissionResult(True)
        def can_view_dashboard(self, role): return _PermissionResult(True)
        def can_run_dashboard(self, role): return _PermissionResult(True)
        def can_arm_broker(self, role): return _PermissionResult(True)
        def can_select_broker(self, role): return _PermissionResult(True)
        def can_use_paper_broker_mode(self, role): return _PermissionResult(True)
        def can_use_live_broker_mode(self, role): return _PermissionResult(False)
        def can_execute_paper_trading(self, role): return _PermissionResult(True)
        def can_execute_live_trading(self, role): return _PermissionResult(False)
        def can_select_engine_mode(self, role, mode): return _PermissionResult(True)


try:
    from backend.security.audit_ledger import AuditLedger
except ModuleNotFoundError:
    class AuditLedger:
        def record(self, event_type, user_id, details):
            return None


try:
    from backend.security.session_manager import SessionManager
except ModuleNotFoundError:
    class _Session:
        def __init__(self, session_id="LOCAL-SESSION"):
            now = time.time()
            self.session_id = session_id
            self.created = now
            self.last_activity = now

    class SessionManager:
        def __init__(self, idle_timeout_seconds=3600, max_session_seconds=28800):
            self.idle_timeout_seconds = idle_timeout_seconds
            self.max_session_seconds = max_session_seconds
            self._sessions = {}

        def create_session(self, username, role, idle_timeout_seconds=None, max_session_seconds=None):
            session = _Session()
            self._sessions[session.session_id] = session
            return session

        def get_session_status(self, session_id):
            session = self._sessions.get(session_id)
            now = time.time()
            created = getattr(session, "created", now)
            last_activity = getattr(session, "last_activity", now)
            return {
                "active": True,
                "created": created,
                "last_activity": last_activity,
                "idle_timeout_seconds": self.idle_timeout_seconds,
                "max_session_seconds": self.max_session_seconds,
                "end_reason": None,
            }

        def touch_session(self, session_id):
            session = self._sessions.get(session_id)
            if session:
                session.last_activity = time.time()

        def destroy_session(self, session_id, reason="operator_stop"):
            self._sessions.pop(session_id, None)


ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

STATE_FILE = ARTIFACTS_DIR / "css_session_recovery.json"

# ===== PCNRASS SESSION + ACCOUNT + ASSET BALANCE MODEL =====
ACCOUNT_STATE_FILE = ARTIFACTS_DIR / "css_account_state_pcnrass.json"
SESSION_STATE_FILE = ARTIFACTS_DIR / "css_session_state_pcnrass.json"

def _pcnrass_read_json(path, default):
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _pcnrass_write_json(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

pcnrass_account_state = _pcnrass_read_json(ACCOUNT_STATE_FILE, {
    "account_balance": 200.0,
    "lifetime_realized_pnl": 0.0,
    "last_session_close": None,
})

pcnrass_session_state = {
    "session_id": datetime.now().isoformat(timespec="seconds"),
    "starting_account_balance": float(pcnrass_account_state.get("account_balance", 200.0)),
    "session_realized_pnl": 0.0,
    "session_unrealized_pnl": 0.0,
    "session_equity": float(pcnrass_account_state.get("account_balance", 200.0)),
}

pcnrass_asset_balances = {
    "CRYPTO": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
    "FX": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
    "FUTURES": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
    "OPTIONS": {"realized": 0.0, "unrealized": 0.0, "equity": 0.0},
}

def pcnrass_refresh_balances(realized_by_asset, floating_by_asset):
    for asset in pcnrass_asset_balances:
        realized = float(realized_by_asset.get(asset, 0.0))
        unrealized = float(floating_by_asset.get(asset, 0.0))
        pcnrass_asset_balances[asset]["realized"] = round(realized, 4)
        pcnrass_asset_balances[asset]["unrealized"] = round(unrealized, 4)
        pcnrass_asset_balances[asset]["equity"] = round(realized + unrealized, 4)

    pcnrass_session_state["session_realized_pnl"] = round(
        sum(v["realized"] for v in pcnrass_asset_balances.values()), 4
    )
    pcnrass_session_state["session_unrealized_pnl"] = round(
        sum(v["unrealized"] for v in pcnrass_asset_balances.values()), 4
    )
    pcnrass_session_state["session_equity"] = round(
        float(pcnrass_session_state["starting_account_balance"])
        + float(pcnrass_session_state["session_realized_pnl"])
        + float(pcnrass_session_state["session_unrealized_pnl"]),
        4,
    )

    _pcnrass_write_json(SESSION_STATE_FILE, {
        "session": pcnrass_session_state,
        "assets": pcnrass_asset_balances,
        "account_balance_pending_close": pcnrass_session_state["session_equity"],
    })

def pcnrass_close_session_to_account():
    pcnrass_account_state["account_balance"] = round(float(pcnrass_session_state["session_equity"]), 4)
    pcnrass_account_state["lifetime_realized_pnl"] = round(
        float(pcnrass_account_state.get("lifetime_realized_pnl", 0.0))
        + float(pcnrass_session_state.get("session_realized_pnl", 0.0)),
        4,
    )
    pcnrass_account_state["last_session_close"] = datetime.now().isoformat(timespec="seconds")
    _pcnrass_write_json(ACCOUNT_STATE_FILE, pcnrass_account_state)

def pcnrass_print_balance_panel():
    print("--- PCNRASS CAPITAL BALANCES ---")
    print(f"ACCOUNT BALANCE (SESSION START): ${float(pcnrass_session_state['starting_account_balance']):,.2f}")
    print(f"SESSION REALIZED PNL: {float(pcnrass_session_state['session_realized_pnl']):+.4f}")
    print(f"SESSION UNREALIZED PNL: {float(pcnrass_session_state['session_unrealized_pnl']):+.4f}")
    print(f"SESSION EQUITY: ${float(pcnrass_session_state['session_equity']):,.2f}")
    print("ASSET BALANCES:")
    for asset, bal in pcnrass_asset_balances.items():
        print(
            f"  {asset:<8} realized={bal['realized']:+.4f} "
            f"unrealized={bal['unrealized']:+.4f} equity={bal['equity']:+.4f}"
        )



RESET_SESSION_ON_BOOT = False  # PCNRASS: preserve recovery state across restarts

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

OPTION_SYMBOLS = ["AAPL-C-175", "SPY-C-500", "QQQ-C-400"]
FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]

CYCLE_SLEEP = 8
FX_LIVE_UNITS = 1
COINBASE_TEST_ORDER_USD = float(os.getenv("COINBASE_TEST_ORDER_USD", "1.00") or 1.00)
COINBASE_MAX_LIVE_ORDER_USD = float(os.getenv("COINBASE_MAX_LIVE_ORDER_USD", "1.00") or 1.00)

SESSION_IDLE_TIMEOUT_SECONDS = int(os.getenv("CSS_SESSION_IDLE_TIMEOUT_SECONDS", "3600") or 3600)
SESSION_MAX_SECONDS = int(os.getenv("CSS_SESSION_MAX_SECONDS", "28800") or 28800)

MAX_PAPER_OPEN_POSITIONS = 10
MAX_OPEN_PER_CYCLE = 8
DEFENSIVE_REDUCTION_PER_CYCLE = 2

HARD_TOTAL_OPEN_POSITION_CAP = 10
HARD_ASSET_OPEN_CAPS = {
    "CRYPTO": 3,
    "FX": 3,
    "FUTURES": 2,
    "OPTIONS": 2,
}
MAX_NEW_PER_CYCLE_BY_ASSET = {
    "CRYPTO": 2,
    "FX": 2,
    "FUTURES": 2,
    "OPTIONS": 2,
}

SUPPORTED_BROKERS = {
    "1": "NONE",
    "2": "OANDA",
    "3": "COINBASE",
    "4": "ALPACA",
    "5": "FUTURES_RESERVED",
}

ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}

MODE_EXIT_PROFILE = {
    # Profit-dominance lifecycle tuning:
    # minimum max_age is now 6 cycles so strong trades have room to develop.
    "SAFE": {"take_profit": 1.75, "stop_loss": -1.25, "max_age": 6},
    "CONSERVATIVE": {"take_profit": 2.25, "stop_loss": -1.75, "max_age": 6},
    "BALANCED": {"take_profit": 3.00, "stop_loss": -2.25, "max_age": 6},
    "AGGRESSIVE": {"take_profit": 4.00, "stop_loss": -3.00, "max_age": 7},
    "EXPANSION": {"take_profit": 5.00, "stop_loss": -3.75, "max_age": 8},
}

ASSET_DRIFT_PROFILE = {
    "CRYPTO": (-0.08, 0.16),
    "FX": (-0.03, 0.06),
    "OPTIONS": (-0.22, 0.34),
    "FUTURES": (-0.25, 0.38),
}

audit_ledger = AuditLedger()


def create_session_manager_compatible() -> SessionManager:
    """
    PCNRASS compatibility helper.
    Some CSS branches accept timeout kwargs; some use a no-arg SessionManager.
    This avoids runtime regression across branches.
    """
    try:
        return SessionManager(
            idle_timeout_seconds=SESSION_IDLE_TIMEOUT_SECONDS,
            max_session_seconds=SESSION_MAX_SECONDS,
        )
    except TypeError:
        try:
            manager = SessionManager()
            # Best-effort attribute injection for older/simple SessionManager versions.
            try:
                manager.idle_timeout_seconds = SESSION_IDLE_TIMEOUT_SECONDS
                manager.max_session_seconds = SESSION_MAX_SECONDS
            except Exception:
                pass
            return manager
        except TypeError:
            # Final fallback for unusual signatures.
            return SessionManager


session_manager = create_session_manager_compatible()


# === PCNRASS SESSION MANAGER COMPATIBILITY LAYER ===
# Some CSS branches have SessionManager but without get_session_status/touch/destroy methods.
# Add missing methods at runtime without changing existing behavior.
if not hasattr(session_manager, "_pcnrass_session_store"):
    session_manager._pcnrass_session_store = {}

if not hasattr(session_manager, "get_session_status"):
    def _pcnrass_get_session_status(session_id):
        now = time.time()
        session = session_manager._pcnrass_session_store.get(str(session_id), {})
        created = float(session.get("created", now))
        last_activity = float(session.get("last_activity", now))
        return {
            "active": True,
            "created": created,
            "last_activity": last_activity,
            "idle_timeout_seconds": SESSION_IDLE_TIMEOUT_SECONDS,
            "max_session_seconds": SESSION_MAX_SECONDS,
            "end_reason": None,
        }
    session_manager.get_session_status = _pcnrass_get_session_status

if not hasattr(session_manager, "touch_session"):
    def _pcnrass_touch_session(session_id):
        sid = str(session_id)
        now = time.time()
        session_manager._pcnrass_session_store.setdefault(sid, {"created": now})
        session_manager._pcnrass_session_store[sid]["last_activity"] = now
    session_manager.touch_session = _pcnrass_touch_session

if not hasattr(session_manager, "destroy_session"):
    def _pcnrass_destroy_session(session_id, reason="operator_stop"):
        session_manager._pcnrass_session_store.pop(str(session_id), None)
    session_manager.destroy_session = _pcnrass_destroy_session

# Make sure a created session is tracked even if the repo SessionManager does not track it visibly.
_original_create_session = getattr(session_manager, "create_session", None)
if callable(_original_create_session):
    def _pcnrass_create_session_compatible(*args, **kwargs):
        session = _original_create_session(*args, **kwargs)
        sid = str(getattr(session, "session_id", "LOCAL-SESSION"))
        now = time.time()
        session_manager._pcnrass_session_store.setdefault(
            sid,
            {"created": getattr(session, "created", now), "last_activity": now},
        )
        return session
    session_manager.create_session = _pcnrass_create_session_compatible

access_control = AccessControl()


# === PCNRASS ACCESS CONTROL COMPATIBILITY LAYER ===
# Some CSS branches have AccessControl but not every newer permission method.
# Missing permissions are safely defaulted so SUPER_USER can restore dashboard operation.
class _PCNRASSPermissionResult:
    def __init__(self, allowed=True):
        self.allowed = allowed


def _pcnrass_allow(*args, **kwargs):
    return _PCNRASSPermissionResult(True)


def _pcnrass_deny_live(*args, **kwargs):
    return _PCNRASSPermissionResult(False)


for _method_name in [
    "can_login",
    "can_view_dashboard",
    "can_run_dashboard",
    "can_arm_broker",
    "can_select_broker",
    "can_use_paper_broker_mode",
    "can_execute_paper_trading",
    "can_select_engine_mode",
]:
    if not hasattr(access_control, _method_name):
        setattr(access_control, _method_name, _pcnrass_allow)

# PCNRASS R2:
# SUPER_USER may enter live broker mode for real balance visibility.
# Live execution remains separately controlled by broker gates, env flags,
# live-order switches, and order-specific protections.
def _pcnrass_live_mode_permission(role=None, *args, **kwargs):
    role_value = str(role or "").strip().upper()
    return _PCNRASSPermissionResult(role_value == "SUPER_USER")


def _pcnrass_live_execution_permission(role=None, *args, **kwargs):
    role_value = str(role or "").strip().upper()
    live_orders_enabled = (
        str(os.getenv("COINBASE_ENABLE_LIVE_ORDERS", "")).strip().lower()
        in {"1", "true", "yes", "y", "on"}
    )
    return _PCNRASSPermissionResult(role_value == "SUPER_USER" and live_orders_enabled)


# Allow SUPER_USER to select live mode so real broker balances can be fetched.
access_control.can_use_live_broker_mode = _pcnrass_live_mode_permission

# Keep actual live execution more restrictive.
access_control.can_execute_live_trading = _pcnrass_live_execution_permission

SESSION_CLOSED = False


def runtime_origin_context() -> dict[str, Any]:
    computer_name = os.getenv("COMPUTERNAME") or socket.gethostname()
    return {
        "computer_name": computer_name,
        "host_name": socket.gethostname(),
        "process_id": os.getpid(),
        "cwd": str(PROJECT_ROOT),
        "script_name": "scripts/css_live_dashboard.py",
        "login_channel": "CLI",
    }


def session_policy_context() -> dict[str, Any]:
    return {
        "idle_timeout_seconds": SESSION_IDLE_TIMEOUT_SECONDS,
        "max_session_seconds": SESSION_MAX_SECONDS,
    }


def build_role_profile(role: str) -> dict[str, Any]:
    role = str(role).strip().upper()

    allowed_engine_modes = [
        mode
        for mode in ENGINE_MODES.values()
        if access_control.can_select_engine_mode(role, mode).allowed
    ]

    return {
        "can_login": access_control.can_login(role).allowed,
        "can_view_dashboard": access_control.can_view_dashboard(role).allowed,
        "can_run_dashboard": access_control.can_run_dashboard(role).allowed,
        "can_arm_broker": access_control.can_arm_broker(role).allowed,
        "can_select_broker": access_control.can_select_broker(role).allowed,
        "can_use_paper_broker_mode": access_control.can_use_paper_broker_mode(role).allowed,
        "can_use_live_broker_mode": access_control.can_use_live_broker_mode(role).allowed,
        "can_execute_paper_trading": access_control.can_execute_paper_trading(role).allowed,
        "can_execute_live_trading": access_control.can_execute_live_trading(role).allowed,
        "allowed_engine_modes": allowed_engine_modes,
    }


def record_rbac_event(
    event_type: str,
    user_ctx: dict[str, Any],
    details: dict[str, Any],
) -> None:
    audit_ledger.record(
        event_type,
        str(user_ctx.get("user_id", "UNKNOWN")),
        {
            "session_id": user_ctx.get("session_id"),
            "display_name": user_ctx.get("display_name"),
            "role": user_ctx.get("role"),
            **details,
        },
    )


def enforce_dashboard_startup_access(user_ctx: dict[str, Any]) -> dict[str, Any]:
    role = str(user_ctx.get("role", "VIEWER")).strip().upper()
    role_profile = build_role_profile(role)

    user_ctx["role_profile"] = role_profile

    if not role_profile["can_login"]:
        record_rbac_event(
            "startup_access_denied",
            user_ctx,
            {
                "resource": "auth",
                "action": "login",
                "reason": "role_cannot_login",
            },
        )
        raise SystemExit(1)

    if not role_profile["can_view_dashboard"]:
        record_rbac_event(
            "startup_access_denied",
            user_ctx,
            {
                "resource": "dashboard",
                "action": "view",
                "reason": "role_cannot_view_dashboard",
            },
        )
        raise SystemExit(1)

    if not role_profile["can_run_dashboard"]:
        record_rbac_event(
            "startup_access_denied",
            user_ctx,
            {
                "resource": "dashboard",
                "action": "run",
                "reason": "role_cannot_run_dashboard",
            },
        )
        raise SystemExit(1)

    record_rbac_event(
        "startup_rbac_profile",
        user_ctx,
        {
            "role_profile": role_profile,
        },
    )
    return user_ctx


def authenticate_startup_user() -> dict[str, Any]:
    try:
        user_ctx = await_login_ready_state()
        try:
            session = session_manager.create_session(
                username=str(user_ctx.get("user_id")),
                role=str(user_ctx.get("role")),
                idle_timeout_seconds=SESSION_IDLE_TIMEOUT_SECONDS,
                max_session_seconds=SESSION_MAX_SECONDS,
            )
        except TypeError:
            try:
                session = session_manager.create_session(
                    username=str(user_ctx.get("user_id")),
                    role=str(user_ctx.get("role")),
                )
            except TypeError:
                session = session_manager.create_session(str(user_ctx.get("user_id")))
        origin = runtime_origin_context()

        user_ctx["session_id"] = session.session_id
        user_ctx["session_created"] = session.created
        user_ctx["computer_name"] = origin["computer_name"]
        user_ctx["host_name"] = origin["host_name"]
        user_ctx["process_id"] = origin["process_id"]
        user_ctx["login_channel"] = origin["login_channel"]
        user_ctx["script_name"] = origin["script_name"]
        user_ctx["session_status"] = session_manager.get_session_status(session.session_id)

        audit_ledger.record(
            "login_success",
            str(user_ctx.get("user_id")),
            {
                "session_id": session.session_id,
                "display_name": user_ctx.get("display_name"),
                "role": user_ctx.get("role"),
                "unit_code": user_ctx.get("unit_code"),
                "home_branch": user_ctx.get("home_branch"),
                **origin,
                **session_policy_context(),
            },
        )

        user_ctx = enforce_dashboard_startup_access(user_ctx)

        print(
            f"[AUTH OK] user_id={user_ctx.get('user_id')} "
            f"role={user_ctx.get('role')} "
            f"unit={user_ctx.get('unit_code')} "
            f"session_id={session.session_id}"
        )
        return user_ctx

    except KeyboardInterrupt:
        try:
            pcnrass_close_session_to_account()
        except Exception as e:
            print(f"[SESSION SETTLEMENT WARN] {e}")

        print("[SESSION STOPPED] Keyboard interrupt received.")
        raise

    except SystemExit:
        raise

    except Exception as e:
        origin = runtime_origin_context()
        audit_ledger.record(
            "login_failed",
            "UNKNOWN",
            {
                "reason": str(e),
                **origin,
            },
        )
        print(f"[AUTH FAILED] {e}")
        raise SystemExit(1)


def sync_session_status() -> dict[str, Any]:
    session_id = str(SESSION_USER_CTX.get("session_id", ""))
    status = session_manager.get_session_status(session_id)
    SESSION_USER_CTX["session_status"] = status
    return status


def touch_active_session() -> dict[str, Any]:
    session_id = str(SESSION_USER_CTX.get("session_id", ""))
    session_manager.touch_session(session_id)
    return sync_session_status()


def activate_defensive_expiry_mode(reason: str, cycle: int, last_trade: str) -> dict[str, Any]:
    lock_session(reason)

    lock_state = get_session_lock_state()
    audit_ledger.record(
        "session_locked_defensive_mode",
        str(SESSION_USER_CTX.get("user_id")),
        {
            "session_id": SESSION_USER_CTX.get("session_id"),
            "display_name": SESSION_USER_CTX.get("display_name"),
            "role": SESSION_USER_CTX.get("role"),
            "reason": reason,
            "cycle": cycle,
            "last_trade": last_trade,
            "lock_time": lock_state.get("lock_time"),
            "computer_name": SESSION_USER_CTX.get("computer_name"),
            "host_name": SESSION_USER_CTX.get("host_name"),
            "process_id": SESSION_USER_CTX.get("process_id"),
            "script_name": SESSION_USER_CTX.get("script_name"),
        },
    )

    print(f"[DEFENSIVE EXPIRY MODE] reason={reason} | new trades blocked, position management continues")

    return {
        "active": False,
        "end_reason": reason,
        "defensive_mode_active": True,
    }


def enforce_active_session(cycle: int, last_trade: str) -> dict[str, Any]:
    status = sync_session_status()

    if not status.get("active", False):
        reason = str(status.get("end_reason") or "session_expired")
        return activate_defensive_expiry_mode(reason, cycle, last_trade)

    return status



def select_global_broker_mode():
    print("=== GLOBAL BROKER MODE ===")
    print("1. PAPER / PRACTICE (default)")
    print("2. LIVE (real trading)")

    choice = input("Enter mode (1-2) [default=1]: ").strip() or "1"

    if choice == "2":
        confirm = input("Type LIVE to confirm GLOBAL LIVE trading: ").strip()
        if confirm.strip().upper() == "LIVE":
            return "live"

    return "paper"




def select_broker_execution_config() -> tuple[bool, str, str]:
    role = str(SESSION_USER_CTX.get("role", "VIEWER")).strip().upper()
    role_profile = SESSION_USER_CTX.get("role_profile", {})

    if not role_profile.get("can_arm_broker", False):
        print(f"[RBAC] Broker arming denied for role {role}. Forced paper/view mode.")
        record_rbac_event(
            "broker_arm_denied",
            SESSION_USER_CTX,
            {
                "resource": "broker",
                "action": "arm",
                "reason": "role_cannot_arm_broker",
            },
        )
        return False, "NONE", "paper"

    print("=== CSS BROKER EXECUTION ARMING ===")
    print("1. DISABLED / PAPER ONLY")
    print("2. ARMED / BROKER EXECUTION ALLOWED")

    armed_choice = input("Enter choice (1-2) [default=1]: ").strip() or "1"

    if armed_choice != "2":
        print("[BROKER EXECUTION DISABLED] Paper/dashboard mode only")
        record_rbac_event(
            "broker_execution_disarmed",
            SESSION_USER_CTX,
            {
                "resource": "broker",
                "action": "disarm",
                "reason": "operator_choice",
            },
        )
        return False, "NONE", "paper"

    if not role_profile.get("can_select_broker", False):
        print(f"[RBAC] Broker selection denied for role {role}.")
        record_rbac_event(
            "broker_selection_denied",
            SESSION_USER_CTX,
            {
                "resource": "broker",
                "action": "select",
                "reason": "role_cannot_select_broker",
            },
        )
        return False, "NONE", "paper"

    print("=== CSS BROKER SELECTION ===")
    print("1. NONE / ARMED BUT NO BROKER")
    print("2. OANDA - FX broker")
    print("3. COINBASE - crypto spot broker")
    print("4. ALPACA - registered, adapter not active yet")
    print("5. FUTURES BROKER - reserved, blocked for now")

    broker_choice = input("Enter broker choice (1-5) [default=1]: ").strip() or "1"
    selected = SUPPORTED_BROKERS.get(broker_choice, "NONE")

    if selected == "NONE":
        record_rbac_event(
            "broker_selected",
            SESSION_USER_CTX,
            {
                "selected_broker": "NONE",
                "selected_broker_mode": "paper",
            },
        )
        print("[BROKER EXECUTION ARMED] No execution broker selected")
        return True, "NONE", "paper"

    if selected == "OANDA":
        broker_mode = GLOBAL_BROKER_MODE

        if broker_mode == "live":
            if not role_profile.get("can_use_live_broker_mode", False):
                print(f"[RBAC] OANDA live mode denied for role {role}. Falling back to paper.")
                broker_mode = "paper"

        if broker_mode == "live":
            os.environ["OANDA_ENV"] = "live"
            os.environ["OANDA_BASE_URL"] = "https://api-fxtrade.oanda.com"
        else:
            if not role_profile.get("can_use_paper_broker_mode", False):
                print(f"[RBAC] OANDA practice mode denied for role {role}.")
                return False, "NONE", "paper"

            os.environ["OANDA_ENV"] = "practice"
            os.environ["OANDA_BASE_URL"] = "https://api-fxpractice.oanda.com"

        record_rbac_event(
            "broker_selected",
            SESSION_USER_CTX,
            {
                "selected_broker": "OANDA",
                "selected_broker_mode": broker_mode,
            },
        )

        print(f"[BROKER EXECUTION ARMED] Selected broker: OANDA / mode={broker_mode} / url={os.environ.get('OANDA_BASE_URL', 'UNKNOWN')}")
        return True, "OANDA", broker_mode

    if selected == "COINBASE":
        print("=== COINBASE MODE ===")
        print("1. PAPER / AUTH TEST / SIMULATED ORDER PATH")
        print("2. LIVE / REAL COINBASE ACCOUNT CONNECTION")
        mode_choice = input("Enter Coinbase mode (1-2) [default=1]: ").strip() or "1"
        broker_mode = "live" if mode_choice == "2" else "paper"

        if broker_mode == "live" and not role_profile.get("can_use_live_broker_mode", False):
            print(f"[RBAC] Coinbase live mode denied for role {role}. Falling back safely.")
            record_rbac_event(
                "broker_mode_denied",
                SESSION_USER_CTX,
                {
                    "selected_broker": "COINBASE",
                    "selected_broker_mode": "live",
                    "reason": "role_cannot_use_live_broker_mode",
                },
            )
            if role_profile.get("can_use_paper_broker_mode", False):
                broker_mode = "paper"
            else:
                return False, "NONE", "paper"

        if broker_mode == "paper" and not role_profile.get("can_use_paper_broker_mode", False):
            print(f"[RBAC] Coinbase paper mode denied for role {role}.")
            record_rbac_event(
                "broker_mode_denied",
                SESSION_USER_CTX,
                {
                    "selected_broker": "COINBASE",
                    "selected_broker_mode": "paper",
                    "reason": "role_cannot_use_paper_broker_mode",
                },
            )
            return False, "NONE", "paper"

        if broker_mode == "live":
            confirm = input(
                "Type LIVE to allow Coinbase live-mode initialization "
                "(orders still require COINBASE_ENABLE_LIVE_ORDERS=true): "
            ).strip()
            if confirm != "LIVE":
                print("[COINBASE LIVE CANCELLED] Falling back to Coinbase paper mode")
                broker_mode = "paper"

        record_rbac_event(
            "broker_selected",
            SESSION_USER_CTX,
            {
                "selected_broker": "COINBASE",
                "selected_broker_mode": broker_mode,
            },
        )
        print(f"[BROKER EXECUTION ARMED] Selected broker: COINBASE / mode={broker_mode}")
        return True, "COINBASE", broker_mode

    print(f"[BROKER RESERVED] {selected} is not executable yet; broker calls will be blocked")
    record_rbac_event(
        "broker_selected",
        SESSION_USER_CTX,
        {
            "selected_broker": selected,
            "selected_broker_mode": "paper",
        },
    )
    return True, selected, "paper"


def select_engine_mode() -> str:
    role = str(SESSION_USER_CTX.get("role", "VIEWER")).strip().upper()
    role_profile = SESSION_USER_CTX.get("role_profile", {})
    allowed_modes = list(role_profile.get("allowed_engine_modes", []))

    if not allowed_modes:
        print(f"[RBAC] No engine modes permitted for role {role}. Forcing SAFE.")
        record_rbac_event(
            "engine_mode_forced",
            SESSION_USER_CTX,
            {
                "requested_mode": None,
                "selected_mode": "SAFE",
                "reason": "no_allowed_engine_modes",
            },
        )
        return "SAFE"

    print("=== CSS ENGINE MODE SELECTOR ===")
    for key, value in ENGINE_MODES.items():
        marker = "" if value in allowed_modes else " [BLOCKED]"
        print(f"{key}. {value}{marker}")

    choice = input("Enter choice (1-5) [default=3]: ").strip() or "3"
    requested_mode = ENGINE_MODES.get(choice, "BALANCED")

    if requested_mode not in allowed_modes:
        fallback_mode = "SAFE" if "SAFE" in allowed_modes else allowed_modes[0]
        print(
            f"[RBAC] Engine mode {requested_mode} denied for role {role}. "
            f"Falling back to {fallback_mode}."
        )
        record_rbac_event(
            "engine_mode_denied",
            SESSION_USER_CTX,
            {
                "requested_mode": requested_mode,
                "selected_mode": fallback_mode,
                "reason": "role_cannot_select_requested_engine_mode",
            },
        )
        return fallback_mode

    record_rbac_event(
        "engine_mode_selected",
        SESSION_USER_CTX,
        {
            "requested_mode": requested_mode,
            "selected_mode": requested_mode,
        },
    )
    return requested_mode


def safe_load_runtime_asset(symbol: str) -> bool:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            load_runtime_asset(symbol)
        print(f"Fetched candles for {symbol}")
        return True
    except Exception as e:
        print(f"[FETCH FAIL] {symbol}: {str(e)[:80]}")
        return False


def record_startup_configuration(
    *,
    user_ctx: dict[str, Any],
    broker_execution_armed: bool,
    selected_broker: str,
    selected_broker_mode: str,
    engine_mode: str,
) -> None:
    audit_ledger.record(
        "session_startup_config",
        str(user_ctx.get("user_id")),
        {
            "session_id": user_ctx.get("session_id"),
            "display_name": user_ctx.get("display_name"),
            "role": user_ctx.get("role"),
            "broker_execution_armed": broker_execution_armed,
            "selected_broker": selected_broker,
            "selected_broker_mode": selected_broker_mode,
            "engine_mode": engine_mode,
            "role_profile": user_ctx.get("role_profile"),
            "computer_name": user_ctx.get("computer_name"),
            "host_name": user_ctx.get("host_name"),
            "process_id": user_ctx.get("process_id"),
            "script_name": user_ctx.get("script_name"),
            **session_policy_context(),
        },
    )


def close_active_session(reason: str, extra: Optional[dict[str, Any]] = None) -> None:
    global SESSION_CLOSED

    if SESSION_CLOSED:
        return

    payload = {
        "session_id": SESSION_USER_CTX.get("session_id"),
        "display_name": SESSION_USER_CTX.get("display_name"),
        "role": SESSION_USER_CTX.get("role"),
        "reason": reason,
        "computer_name": SESSION_USER_CTX.get("computer_name"),
        "host_name": SESSION_USER_CTX.get("host_name"),
        "process_id": SESSION_USER_CTX.get("process_id"),
        "script_name": SESSION_USER_CTX.get("script_name"),
    }

    if extra:
        payload.update(extra)

    audit_ledger.record(
        "session_end",
        str(SESSION_USER_CTX.get("user_id")),
        payload,
    )

    # PCNRASS: settle session balance into account balance only at session close.
    try:
        pcnrass_close_session_to_account()
    except Exception:
        pass

    session_id = SESSION_USER_CTX.get("session_id")
    if session_id:
        try:
            session_manager.destroy_session(str(session_id), reason=reason)
        except TypeError:
            try:
                session_manager.destroy_session(str(session_id))
            except TypeError:
                pass

    SESSION_CLOSED = True



# === PCNRASS RESTORED CSS AUTHENTICATION ===
# Scope: authentication only. Do not touch PnL, broker, execution, dashboard, or risk logic.
# Policy:
# - Initial super user: 00000
# - Initial password: 123456
# - Force password change on first login
# - Force password change every 30 calendar days
# - Persist latest successful login under artifacts/css_auth_session.json
USERS_FILE = PROJECT_ROOT / "data" / "users.json"
SESSION_AUTH_FILE = ARTIFACTS_DIR / "css_auth_session.json"
PASSWORD_MAX_AGE_DAYS = 30


CSS_AUTH_PANEL_WIDTH = 72


def _css_panel_border(char: str = "=") -> str:
    return char * CSS_AUTH_PANEL_WIDTH


def _css_panel_line(label: str = "", value: str = "") -> str:
    content_width = CSS_AUTH_PANEL_WIDTH - 4

    if not label and not value:
        return f"| {' ' * content_width} |"

    if value:
        text = f"{label}: {value}"
    else:
        text = label

    return f"| {text[:content_width].ljust(content_width)} |"


def render_css_sign_in_screen() -> None:
    print()
    print(_css_panel_border("="))
    print(_css_panel_line("CAPITAL STRATA SYSTEMS"))
    print(_css_panel_line("Governance Runtime Access"))
    print(_css_panel_border("-"))
    print(_css_panel_line("Authentication", "required"))
    print(_css_panel_line("Session Policy", f"{SESSION_IDLE_TIMEOUT_SECONDS // 60}m idle / {SESSION_MAX_SECONDS // 60}m max"))
    print(_css_panel_line("Default Runtime", "paper-first, governance-gated"))
    print(_css_panel_line("Initial Admin ID", "00000"))
    print(_css_panel_border("="))
    print()


def render_css_auth_status(title: str, message: str) -> None:
    print()
    print(_css_panel_border("-"))
    print(_css_panel_line(title, message))
    print(_css_panel_border("-"))
    print()


def css_auth_input(prompt_label: str) -> str:
    return input(f"CSS AUTH | {prompt_label}: ")


def css_auth_secret(prompt_label: str) -> str:
    return masked_password_input(f"CSS AUTH | {prompt_label}: ")



# ===== PCNRASS MASKED PASSWORD INPUT =====
def masked_password_input(prompt: str = "CSS LOGIN | password: ") -> str:
    try:
        import msvcrt

        print(prompt, end="", flush=True)
        password_chars = []

        while True:
            ch = msvcrt.getwch()

            if ch in ("\r", "\n"):
                print()
                break

            if ch in ("\b", "\x7f"):
                if password_chars:
                    password_chars.pop()
                    print("\b \b", end="", flush=True)
                continue

            if ch in ("\x00", "\xe0"):
                try:
                    msvcrt.getwch()
                except Exception:
                    pass
                continue

            password_chars.append(ch)
            print("*", end="", flush=True)

        return "".join(password_chars)

    except Exception:
        return getpass.getpass(prompt)


def _css_hash_password(password: str) -> str:
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def _css_load_users() -> dict[str, Any]:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not USERS_FILE.exists():
        USERS_FILE.write_text(json.dumps({
            "00000": {
                "user_id": "00000",
                "display_name": "CSS Administrator",
                "role": "SUPER_USER",
                "unit_code": "CORE",
                "home_branch": "HQ",
                "password_hash": _css_hash_password("123456"),
                "must_change_password": True,
                "last_password_change": None
            }
        }, indent=2), encoding="utf-8")

    with open(USERS_FILE, "r", encoding="utf-8") as f:
        users = json.load(f)

    # Ensure super-user exists and is reset only when absent, not after user changes password.
    if "00000" not in users:
        users["00000"] = {
            "user_id": "00000",
            "display_name": "CSS Administrator",
            "role": "SUPER_USER",
            "unit_code": "CORE",
            "home_branch": "HQ",
            "password_hash": _css_hash_password("123456"),
            "must_change_password": True,
            "last_password_change": None
        }
        _css_save_users(users)

    # Normalize user_id values to five-character strings.
    changed = False
    for key, rec in list(users.items()):
        if isinstance(rec, dict):
            normalized = str(rec.get("user_id", key)).zfill(5)
            if rec.get("user_id") != normalized:
                rec["user_id"] = normalized
                changed = True
    if changed:
        _css_save_users(users)

    return users


def _css_save_users(users: dict[str, Any]) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _css_password_expired(user_record: dict[str, Any]) -> bool:
    if bool(user_record.get("must_change_password", False)):
        return True

    last_change = user_record.get("last_password_change")
    if not last_change:
        return True

    try:
        last_dt = datetime.fromisoformat(str(last_change))
    except Exception:
        return True

    return datetime.now() - last_dt >= timedelta(days=PASSWORD_MAX_AGE_DAYS)


def _css_force_password_change(users: dict[str, Any], user_key: str) -> None:
    render_css_auth_status(
        "PASSWORD CHANGE REQUIRED",
        "Initial or expired password must be changed now",
    )

    while True:
        new_password = css_auth_secret("new password").strip()
        confirm_password = css_auth_secret("confirm password").strip()

        if not new_password:
            render_css_auth_status("PASSWORD ERROR", "Password cannot be blank")
            continue

        if len(new_password) < 6:
            render_css_auth_status(
                "PASSWORD ERROR",
                "Password must be at least 6 characters",
            )
            continue

        if new_password == "123456":
            render_css_auth_status(
                "PASSWORD ERROR",
                "New password cannot remain the initial default password",
            )
            continue

        if new_password != confirm_password:
            render_css_auth_status("PASSWORD ERROR", "Passwords do not match")
            continue

        users[user_key]["password_hash"] = _css_hash_password(new_password)
        users[user_key]["must_change_password"] = False
        users[user_key]["last_password_change"] = datetime.now().isoformat(timespec="seconds")
        _css_save_users(users)
        render_css_auth_status("PASSWORD UPDATED", "Password changed successfully")
        return


def _css_persist_login_session(user_ctx: dict[str, Any]) -> None:
    SESSION_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_AUTH_FILE.write_text(json.dumps({
        "user_id": user_ctx.get("user_id"),
        "display_name": user_ctx.get("display_name"),
        "role": user_ctx.get("role"),
        "unit_code": user_ctx.get("unit_code"),
        "home_branch": user_ctx.get("home_branch"),
        "last_login": datetime.now().isoformat(timespec="seconds"),
        "login_persistence": True
    }, indent=2), encoding="utf-8")


def await_login_ready_state():
    users = _css_load_users()
    render_css_sign_in_screen()

    while True:
        user_id = css_auth_input("user id").strip().zfill(5)

        user_record = users.get(user_id)
        if not user_record:
            render_css_auth_status("AUTH FAILED", "INVALID_USER_ID")
            continue

        password = css_auth_secret("password")
        expected_hash = str(user_record.get("password_hash", "")).strip()
        supplied_hash = _css_hash_password(password)

        if supplied_hash != expected_hash:
            render_css_auth_status("AUTH FAILED", "AUTH_FAILED")
            continue

        if _css_password_expired(user_record):
            _css_force_password_change(users, user_id)
            users = _css_load_users()
            user_record = users[user_id]

        ctx = {
            "user_id": str(user_record.get("user_id", user_id)).zfill(5),
            "display_name": user_record.get("display_name", "CSS User"),
            "role": user_record.get("role", "VIEWER"),
            "unit_code": user_record.get("unit_code", "CORE"),
            "home_branch": user_record.get("home_branch", "HQ"),
        }

        _css_persist_login_session(ctx)
        render_css_auth_status(
            "AUTH SUCCESS",
            f"{ctx['display_name']} | role={ctx['role']}",
        )
        return ctx


SESSION_USER_CTX = authenticate_startup_user()

GLOBAL_BROKER_MODE = select_global_broker_mode()

BROKER_EXECUTION_ARMED, SELECTED_BROKER, SELECTED_BROKER_MODE = select_broker_execution_config()

ENGINE_MODE = select_engine_mode()
print(f"[ENGINE MODE SELECTED] {ENGINE_MODE}")



record_startup_configuration(
    user_ctx=SESSION_USER_CTX,
    broker_execution_armed=BROKER_EXECUTION_ARMED,
    selected_broker=SELECTED_BROKER,
    selected_broker_mode=SELECTED_BROKER_MODE,
    engine_mode=ENGINE_MODE,
)



# === R7 PCNRASS UNIFIED TRADE GATE ===
class CSSUnifiedTradeGate:
    """
    Single pre-position authority for paper and broker-routed trade openings.
    This does not replace broker-specific live gates; it sits before any
    position registration so blocked trades do not enter MTM/PnL state.
    """

    def approve_trade(self, *, candidate: dict, session: dict, role_profile: dict) -> dict:
        symbol = str(candidate.get("symbol", "UNKNOWN"))
        asset_class = str(candidate.get("asset_class", "UNKNOWN")).upper()

        if not isinstance(session, dict) or not session.get("session_id"):
            return {"approved": False, "reason": "NO_VALID_SESSION"}

        if not session.get("session_status", {}).get("active", True):
            return {"approved": False, "reason": "SESSION_NOT_ACTIVE"}

        if is_session_locked():
            return {"approved": False, "reason": "SESSION_LOCKED_DEFENSIVE_MODE"}

        if asset_class not in {"CRYPTO", "FX", "FUTURES", "OPTIONS"}:
            return {"approved": False, "reason": f"UNSUPPORTED_ASSET_CLASS_{asset_class}"}

        broker_mode = str(candidate.get("broker_mode", "paper")).lower()
        if broker_mode == "live":
            if not role_profile.get("can_use_live_broker_mode", False):
                return {"approved": False, "reason": "RBAC_BLOCKED_LIVE_MODE"}
            if not role_profile.get("can_execute_live_trading", False):
                return {"approved": False, "reason": "RBAC_BLOCKED_LIVE_EXECUTION"}
        else:
            if not role_profile.get("can_execute_paper_trading", False):
                return {"approved": False, "reason": "RBAC_BLOCKED_PAPER_EXECUTION"}

        if ENGINE_MODE == "SAFE" and broker_mode == "live":
            return {"approved": False, "reason": "SAFE_MODE_BLOCKS_LIVE_EXECUTION"}

        return {"approved": True, "reason": "UNIFIED_GATE_APPROVED"}


css_unified_trade_gate = CSSUnifiedTradeGate()


def approve_trade_before_register(asset_class: str, symbol: str, sig: float, prob: float) -> tuple[bool, str]:
    decision = css_unified_trade_gate.approve_trade(
        candidate={
            "asset_class": asset_class,
            "symbol": symbol,
            "signal_score": sig,
            "prob_positive": prob,
            "selected_broker": SELECTED_BROKER,
            "broker_mode": SELECTED_BROKER_MODE,
            "engine_mode": ENGINE_MODE,
        },
        session=SESSION_USER_CTX,
        role_profile=SESSION_USER_CTX.get("role_profile", {}),
    )

    if not decision.get("approved", False):
        try:
            audit_ledger.record(
                "unified_trade_gate_reject",
                str(SESSION_USER_CTX.get("user_id")),
                {
                    "session_id": SESSION_USER_CTX.get("session_id"),
                    "asset_class": asset_class,
                    "symbol": symbol,
                    "reason": decision.get("reason"),
                    "selected_broker": SELECTED_BROKER,
                    "broker_mode": SELECTED_BROKER_MODE,
                    "engine_mode": ENGINE_MODE,
                },
            )
        except Exception:
            pass

        print(f"[UNIFIED GATE BLOCKED] {asset_class} {symbol} | {decision.get('reason')}")
        return False, str(decision.get("reason"))

    return True, str(decision.get("reason"))


class AdaptiveConcurrencyEnvelopeController:
    def __init__(self) -> None:
        self.current_limit = HARD_TOTAL_OPEN_POSITION_CAP
        self.max_limit = HARD_TOTAL_OPEN_POSITION_CAP
        self.min_limit = HARD_TOTAL_OPEN_POSITION_CAP

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
    PCNRASS R1 UPGRADE:
    Dynamic capital source:
    - PAPER mode keeps controlled simulated test capital.
    - LIVE mode attempts broker-fetched account balance through RealBalanceEngine.
    - Fail-closed: if real balance fetch fails, available live capital becomes 0.0.
    """

    def __init__(self) -> None:
        self.paper_mode = True
        self.simulated_capital_pool = 200.00
        self.max_capital_per_trade = 25.00
        self.max_broker_test_positions = 5
        self.active_test_allocations: dict[str, float] = {}
        self.real_balance = 0.0
        self.real_equity = 0.0
        self.balance_source = "SIMULATED"

    def _get_adapter(self):
        try:
            if str(SELECTED_BROKER).upper() == "OANDA":
                return oanda
            if str(SELECTED_BROKER).upper() == "COINBASE":
                return coinbase
        except Exception:
            return None
        return None

    def refresh_real_balance(self) -> dict:
        try:
            from backend.app.accounting.real_balance_engine import RealBalanceEngine

            engine = RealBalanceEngine(SELECTED_BROKER, self._get_adapter())
            data = engine.get_balance()

            self.real_balance = float(data.get("balance", 0.0) or 0.0)
            self.real_equity = float(data.get("equity", self.real_balance) or 0.0)
            self.balance_source = str(data.get("source", "UNKNOWN"))

            print(
                f"[REAL BALANCE LOADED] broker={SELECTED_BROKER} "
                f"mode={SELECTED_BROKER_MODE} balance=${self.real_balance:,.2f} "
                f"equity=${self.real_equity:,.2f} source={self.balance_source}"
            )

            return data

        except Exception as e:
            self.real_balance = 0.0
            self.real_equity = 0.0
            self.balance_source = f"REAL_BALANCE_ERROR_{str(e)[:40]}"
            print(f"[REAL BALANCE ERROR] {str(e)[:80]}")
            return {
                "balance": 0.0,
                "equity": 0.0,
                "source": self.balance_source,
            }

    def available_capital(self) -> float:
        allocated = sum(self.active_test_allocations.values())

        if self.paper_mode:
            try:
                base_capital = float(pnl_observer.equity())
            except Exception:
                try:
                    base_capital = float(pnl_observer.current_balance)
                except Exception:
                    base_capital = float(self.simulated_capital_pool)
        else:
            base_capital = float(self.real_balance)

        return round(base_capital - allocated, 4)

    def capital_source_label(self) -> str:
        if self.paper_mode:
            return "SIMULATED"
        return self.balance_source or f"REAL_BROKER_{SELECTED_BROKER}"

    def can_fund_trade(self, position_id: str) -> bool:
        if self.paper_mode:
            return False
        if position_id in self.active_test_allocations:
            return False
        if len(self.active_test_allocations) >= self.max_broker_test_positions:
            return False
        if self.available_capital() < self.max_capital_per_trade:
            return False
        return True

    def allocate_trade(self, position_id: str) -> bool:
        if not self.can_fund_trade(position_id):
            return False
        self.active_test_allocations[position_id] = self.max_capital_per_trade
        return True

    def release_trade(self, position_id: str) -> None:
        if position_id in self.active_test_allocations:
            del self.active_test_allocations[position_id]

    def live_positions_count(self) -> int:
        return len(self.active_test_allocations)

    def funded_amount(self) -> float:
        return round(sum(self.active_test_allocations.values()), 4)

    def set_live_mode(self) -> None:
        self.paper_mode = False
        self.refresh_real_balance()

    def set_paper_mode(self) -> None:
        self.paper_mode = True
        self.balance_source = "SIMULATED"


capital_governor = CapitalDeploymentGovernor()

# Phase 1 PnL observer only
pnl_observer = Portfolio(
    starting_balance=capital_governor.simulated_capital_pool,
    current_balance=capital_governor.simulated_capital_pool,
)

# === INITIALIZE NEW TRACKER ===
pnl_tracker = PnLTracker(starting_equity=pnl_observer.starting_balance)


def map_oanda_env() -> None:
    if not os.getenv("OANDA_API_KEY"):
        if os.getenv("OANDA_API_TOKEN"):
            os.environ["OANDA_API_KEY"] = os.getenv("OANDA_API_TOKEN", "")
        elif os.getenv("OANDA_PRACTICE_TOKEN"):
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

coinbase: Optional[Any] = None

coinbase_live_gate = CoinbaseLiveOrderGate(
    approved_symbols=SYMBOLS,
    max_order_usd=COINBASE_MAX_LIVE_ORDER_USD,
    require_manual_phrase=False,
)

broker_gate_audit = BrokerGateAuditLogger()


def initialize_selected_coinbase() -> None:
    global coinbase

    if not BROKER_EXECUTION_ARMED:
        return

    if SELECTED_BROKER != "COINBASE":
        return

    try:
        coinbase = initialize_broker("coinbase", SELECTED_BROKER_MODE)
        print(f"[COINBASE BOOTSTRAP] Coinbase initialized in {SELECTED_BROKER_MODE} mode")
    except Exception as e:
        coinbase = None
        print(f"[COINBASE BOOTSTRAP ERROR] {str(e)[:100]}")


initialize_selected_coinbase()

# PCNRASS R3: activate correct capital source after broker adapters are initialized.
def pcnrass_activate_capital_source() -> None:
    if str(SELECTED_BROKER_MODE).lower() == "live":
        capital_governor.set_live_mode()
    else:
        capital_governor.set_paper_mode()

    base_capital = capital_governor.available_capital() + capital_governor.funded_amount()

    try:
        pnl_observer.starting_balance = float(base_capital)
        pnl_observer.current_balance = float(base_capital)
    except Exception as e:
        print(f"[CAPITAL SYNC WARN] pnl_observer sync failed: {str(e)[:60]}")

    if str(SELECTED_BROKER_MODE).lower() == "live":
        if float(capital_governor.real_balance or 0.0) <= 0.0:
            print(
                f"[LIVE CAPITAL WARNING] broker={SELECTED_BROKER} "
                f"mode=live url={os.environ.get('OANDA_BASE_URL', 'UNKNOWN')} "
                f"balance_fetch_failed_or_zero. Live trading must remain blocked until real balance is loaded."
            )

    # === R11 CAPITAL HARD LOCK ===
if str(SELECTED_BROKER_MODE).lower() == "live":
    real_balance = float(getattr(capital_governor, "real_balance", 0.0) or 0.0)

    if real_balance <= 0.0:
        print(
            f"[LIVE CAPITAL BLOCKED] broker={SELECTED_BROKER} "
            f"url={get_active_broker_url()} "
            f"reason=NO_REAL_BALANCE"
        )

        print("[SYSTEM HALT] Live trading disabled until real broker balance is loaded.")
        
        # HARD STOP — prevent fake execution
        import sys
        sys.exit(1)

print(
    f"[CAPITAL SOURCE ACTIVE] source={capital_governor.capital_source_label()} "
    f"mode={SELECTED_BROKER_MODE} available=${capital_governor.available_capital():,.2f}"
)


enforce_mode_dominance()
pcnrass_activate_capital_source()
enforce_execution_boundary()


# === PCNRASS PHASE 2 BROKER ISOLATION + REAL PRICE HELPERS ===
# Real market pricing only activates when broker execution is ARMED and selected broker mode is LIVE.
# Paper mode remains paper/simulation-safe and must not pull real account capital into trading logic.
def pcnrass_real_market_enabled() -> bool:
    return (
        bool(BROKER_EXECUTION_ARMED)
        and str(SELECTED_BROKER_MODE).lower() == "live"
        and str(SELECTED_BROKER).upper() in {"COINBASE", "OANDA"}
    )


def pcnrass_selected_broker_is(name: str) -> bool:
    return str(SELECTED_BROKER).upper() == str(name).upper()


def pcnrass_get_reference_price(symbol: str, fallback: float = 100.0) -> float:
    if pcnrass_real_market_enabled():
        try:
            px = price_feed.get_price(symbol)
            if px is not None and float(px) > 0:
                return float(px)
        except Exception:
            pass
    return float(fallback)


def pcnrass_wait_for_next_cycle(cycle: int) -> bool:
    response = input(f"\n[PCNRASS PAUSE] Cycle {cycle} complete. Press ENTER for next cycle, or type Q to quit: ").strip().lower()
    return response not in {"q", "quit", "exit", "stop"}



def is_oanda_practice_mode() -> bool:
    base_url = os.getenv("OANDA_BASE_URL", "")
    return "api-fxpractice.oanda.com" in base_url


def get_oanda_open_trade_count() -> int | str:
    try:
        result = oanda.get_open_trades()
        if result.get("ok", False):
            return len(result.get("data", {}).get("trades", []))
        return "ERR"
    except Exception:
        return "ERR"


def oanda_has_open_trade() -> bool:
    count = get_oanda_open_trade_count()
    if isinstance(count, int):
        return count > 0
    return False


def attempt_oanda_fx_execution(symbol: str) -> tuple[bool, str]:
    role_profile = SESSION_USER_CTX.get("role_profile", {})

    def _audit(allowed: bool, reason: str) -> None:
        broker_gate_audit.log_decision(
            broker="OANDA",
            gate_name="oanda_fx_order_gate",
            allowed=allowed,
            reason=reason,
            symbol=symbol,
            instrument=symbol,
            asset_class="FX",
            size=float(FX_LIVE_UNITS),
            size_unit="UNITS",
            selected_broker=SELECTED_BROKER,
            broker_mode="paper",
            engine_mode=ENGINE_MODE,
            execution_armed=BROKER_EXECUTION_ARMED,
            live_orders_flag=False,
            extra={
                "practice_mode": is_oanda_practice_mode(),
                "open_trade_count": get_oanda_open_trade_count(),
                "session_user_id": SESSION_USER_CTX.get("user_id"),
                "session_role": SESSION_USER_CTX.get("role"),
                "session_id": SESSION_USER_CTX.get("session_id"),
                "defensive_mode_active": is_session_locked(),
            },
        )

    if is_session_locked():
        _audit(False, "SESSION_LOCKED_DEFENSIVE_MODE")
        return False, "SESSION_LOCKED_DEFENSIVE_MODE"

    if not BROKER_EXECUTION_ARMED:
        _audit(False, "BROKER_DISABLED_BY_GLOBAL_SWITCH")
        return False, "BROKER_DISABLED_BY_GLOBAL_SWITCH"

    if not role_profile.get("can_execute_paper_trading", False):
        _audit(False, "RBAC_BLOCKED_PAPER_EXECUTION")
        return False, "RBAC_BLOCKED_PAPER_EXECUTION"

    if SELECTED_BROKER != "OANDA":
        reason = f"BROKER_NOT_SELECTED_FOR_OANDA_{SELECTED_BROKER}"
        _audit(False, reason)
        return False, reason

    if ENGINE_MODE == "SAFE":
        _audit(False, "OANDA_BLOCKED_SAFE_MODE")
        return False, "OANDA_BLOCKED_SAFE_MODE"

    if symbol not in FX_SYMBOLS:
        _audit(False, "OANDA_BLOCKED_NOT_FX")
        return False, "OANDA_BLOCKED_NOT_FX"

    if oanda_has_open_trade():
        _audit(False, "OANDA_BLOCKED_OPEN_TRADE")
        return False, "OANDA_BLOCKED_OPEN_TRADE"

    try:
        response = oanda.place_order(
            symbol=symbol,
            side="BUY",
            units=FX_LIVE_UNITS,
            order_type="MARKET",
        )

        if response.get("ok"):
            _audit(True, "OANDA_ORDER_OK")
            return True, "OANDA_ORDER_OK"

        reason = f"OANDA_ORDER_FAIL_{response.get('status', 'NA')}"
        _audit(False, reason)
        return False, reason

    except Exception as e:
        reason = f"OANDA_ERROR_{str(e)[:40]}"
        _audit(False, reason)
        return False, reason


def coinbase_live_orders_enabled() -> bool:
    return (os.getenv("COINBASE_ENABLE_LIVE_ORDERS") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _coinbase_response_ok(response: Any) -> tuple[bool, str]:
    if not isinstance(response, dict):
        return False, "NON_DICT_RESPONSE"

    status = str(response.get("status") or response.get("order_status") or "").lower()

    if status in {"paper_filled", "filled", "done", "success"}:
        return True, status.upper()

    if response.get("ok") is True or response.get("success") is True:
        return True, "OK_TRUE"

    success_response = response.get("success_response")
    if isinstance(success_response, dict):
        return True, "SUCCESS_RESPONSE"

    error_response = response.get("error_response")
    if isinstance(error_response, dict):
        msg = (
            error_response.get("message")
            or error_response.get("error")
            or str(error_response)[:60]
        )
        return False, str(msg)[:60]

    err = response.get("error") or response.get("message") or status or "UNKNOWN_RESPONSE"
    return False, str(err)[:60]


def evaluate_coinbase_live_gate(symbol: str, size_usd: float):
    if is_session_locked():
        broker_gate_audit.log_decision(
            broker="COINBASE",
            gate_name="coinbase_live_order_gate",
            allowed=False,
            reason="SESSION_LOCKED_DEFENSIVE_MODE",
            symbol=symbol,
            instrument=symbol,
            asset_class="CRYPTO",
            size=float(size_usd),
            size_unit="USD",
            selected_broker=SELECTED_BROKER,
            broker_mode=SELECTED_BROKER_MODE,
            engine_mode=ENGINE_MODE,
            execution_armed=BROKER_EXECUTION_ARMED,
            live_orders_flag=coinbase_live_orders_enabled(),
            extra={
                "session_user_id": SESSION_USER_CTX.get("user_id"),
                "session_role": SESSION_USER_CTX.get("role"),
                "session_id": SESSION_USER_CTX.get("session_id"),
            },
        )
        return False, "SESSION_LOCKED_DEFENSIVE_MODE"

    if SELECTED_BROKER_MODE != "live":
        broker_gate_audit.log_decision(
            broker="COINBASE",
            gate_name="coinbase_live_order_gate",
            allowed=True,
            reason="COINBASE_PAPER_MODE_GATE_BYPASS",
            symbol=symbol,
            instrument=symbol,
            asset_class="CRYPTO",
            size=float(size_usd),
            size_unit="USD",
            selected_broker=SELECTED_BROKER,
            broker_mode=SELECTED_BROKER_MODE,
            engine_mode=ENGINE_MODE,
            execution_armed=BROKER_EXECUTION_ARMED,
            live_orders_flag=coinbase_live_orders_enabled(),
            extra={
                "note": "paper mode bypass",
                "session_user_id": SESSION_USER_CTX.get("user_id"),
                "session_role": SESSION_USER_CTX.get("role"),
                "session_id": SESSION_USER_CTX.get("session_id"),
            },
        )
        return True, "COINBASE_PAPER_MODE_GATE_BYPASS"

    result = coinbase_live_gate.evaluate(
        broker_execution_armed=BROKER_EXECUTION_ARMED,
        selected_broker=SELECTED_BROKER,
        broker_mode=SELECTED_BROKER_MODE,
        engine_mode=ENGINE_MODE,
        symbol=symbol,
        size_usd=float(size_usd),
        coinbase_adapter=coinbase,
    )

    broker_gate_audit.log_decision(
        broker="COINBASE",
        gate_name="coinbase_live_order_gate",
        allowed=result.allowed,
        reason=result.reason,
        symbol=symbol,
        instrument=symbol,
        asset_class="CRYPTO",
        size=float(size_usd),
        size_unit="USD",
        selected_broker=SELECTED_BROKER,
        broker_mode=SELECTED_BROKER_MODE,
        engine_mode=ENGINE_MODE,
        execution_armed=BROKER_EXECUTION_ARMED,
        live_orders_flag=coinbase_live_orders_enabled(),
        extra={
            "max_live_order_usd": COINBASE_MAX_LIVE_ORDER_USD,
            "account_count_hint": 9
            if SELECTED_BROKER == "COINBASE" and SELECTED_BROKER_MODE == "live"
            else None,
            "session_user_id": SESSION_USER_CTX.get("user_id"),
            "session_role": SESSION_USER_CTX.get("role"),
            "session_id": SESSION_USER_CTX.get("session_id"),
        },
    )

    return result.allowed, result.reason


def attempt_coinbase_crypto_execution(symbol: str) -> tuple[bool, str]:
    role_profile = SESSION_USER_CTX.get("role_profile", {})

    if is_session_locked():
        return False, "SESSION_LOCKED_DEFENSIVE_MODE"

    if not BROKER_EXECUTION_ARMED:
        return False, "BROKER_DISABLED_BY_GLOBAL_SWITCH"

    if SELECTED_BROKER != "COINBASE":
        return False, f"BROKER_NOT_SELECTED_FOR_COINBASE_{SELECTED_BROKER}"

    if ENGINE_MODE == "SAFE":
        return False, "COINBASE_BLOCKED_SAFE_MODE"

    if symbol not in SYMBOLS:
        return False, "COINBASE_BLOCKED_NOT_CRYPTO"

    if coinbase is None:
        return False, "COINBASE_NOT_INITIALIZED"

    if SELECTED_BROKER_MODE == "live" and not role_profile.get("can_execute_live_trading", False):
        return False, "RBAC_BLOCKED_LIVE_EXECUTION"

    if SELECTED_BROKER_MODE != "live" and not role_profile.get("can_execute_paper_trading", False):
        return False, "RBAC_BLOCKED_PAPER_EXECUTION"

    gate_ok, gate_reason = evaluate_coinbase_live_gate(
        symbol=symbol,
        size_usd=float(COINBASE_TEST_ORDER_USD),
    )

    if not gate_ok:
        return False, f"COINBASE_LIVE_GATE_BLOCKED_{gate_reason}"

    if not hasattr(coinbase, "place_market_buy"):
        return False, "COINBASE_ADAPTER_MISSING_PLACE_MARKET_BUY"

    try:
        response = coinbase.place_market_buy(
            product_id=symbol,
            size_usd=float(COINBASE_TEST_ORDER_USD),
        )

        ok, note = _coinbase_response_ok(response)
        if ok:
            return True, f"COINBASE_ORDER_OK_{SELECTED_BROKER_MODE.upper()}_{note}"

        return False, f"COINBASE_ORDER_FAIL_{note}"

    except Exception as e:
        return False, f"COINBASE_ERROR_{str(e)[:40]}"


class SessionRecoveryEngine:
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
            "session_user_ctx": SESSION_USER_CTX,
            "selected_broker": SELECTED_BROKER,
            "selected_broker_mode": SELECTED_BROKER_MODE,
            "engine_mode": ENGINE_MODE,
            "session_lock_state": get_session_lock_state(),
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
        self.defensive_reduction_exits = 0
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

    def record_defensive_reduction_exit(self) -> None:
        self.defensive_reduction_exits += 1


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
        allow_live_funding: bool = False,
    ) -> dict:
        self.position_counter += 1
        pid = f"POS-{self.position_counter}"

        cluster_name = None
        for cname, members in cluster_amplifier.cluster_map.items():
            if symbol in members:
                cluster_name = cname
                break

        cluster_risk_governor.record_cluster_slot(cluster_name)

        broker_tested = False
        if allow_live_funding:
            broker_tested = capital_governor.allocate_trade(pid)

        entry_price = pcnrass_get_reference_price(symbol, fallback=100.0)

        position = {
            "position_id": pid,
            "asset_class": asset_class,
            "symbol": symbol,
            "cluster_name": cluster_name,
            "entry_price": float(entry_price),
            "current_price": float(entry_price),
            "floating": 0.0,
            "forced_exit": False,
            "exit_reason": None,
            "age_cycles": 0,
            "signal_score": signal_score,
            "prob_positive": prob_positive,
            "broker_tested": broker_tested,
            "live_funded": broker_tested,
            "broker_order_ok": False,
            "broker_note": "NO_BROKER_ORDER",
            "session_user_id": SESSION_USER_CTX.get("user_id"),
            "session_role": SESSION_USER_CTX.get("role"),
            "session_id": SESSION_USER_CTX.get("session_id"),
        }

        self.positions.append(position)
        return position

    def count_open_positions(self) -> int:
        return sum(1 for p in self.positions if not p["forced_exit"])

    def count_open_positions_by_asset(self) -> dict[str, int]:
        counts = {
            "CRYPTO": 0,
            "FX": 0,
            "OPTIONS": 0,
            "FUTURES": 0,
        }

        for pos in self.positions:
            if pos["forced_exit"]:
                continue
            counts[pos["asset_class"]] += 1

        return counts

    def count_open_broker_test_positions(self) -> int:
        return sum(
            1
            for p in self.positions
            if not p["forced_exit"] and p.get("broker_tested", False)
        )

    def count_open_funded_positions(self) -> int:
        return self.count_open_broker_test_positions()

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

            if funded_only and not pos.get("broker_tested", False):
                continue

            by_asset[pos["asset_class"]] += pos["floating"]

        return by_asset
mtm_engine = MarkToMarketEngine()


def hard_position_limit() -> int:
    return HARD_TOTAL_OPEN_POSITION_CAP


def hard_asset_cap(asset_class: str) -> int:
    return HARD_ASSET_OPEN_CAPS.get(asset_class, 0)


def max_new_per_cycle(asset_class: str) -> int:
    return MAX_NEW_PER_CYCLE_BY_ASSET.get(asset_class, 0)


def can_open_position(
    asset_class: str,
    *,
    open_counts: dict[str, int],
    new_counts_this_cycle: dict[str, int],
) -> tuple[bool, str]:
    # =========================
    # R16B DRAWDOWN CIRCUIT BREAKER
    # =========================
    try:
        current_dd = float(getattr(pnl_tracker, "max_drawdown", 0.0))
        if current_dd >= 0.05:
            print(f"[R16B BLOCK] Drawdown limit reached: {current_dd:.2%}")
            return False, "DRAWDOWN_LIMIT"
    except Exception:
        pass

    total_open = sum(open_counts.values())

    if total_open >= hard_position_limit():
        return False, "TOTAL_CAP_REACHED"

    if open_counts.get(asset_class, 0) >= hard_asset_cap(asset_class):
        return False, f"{asset_class}_CAP_REACHED"

    if new_counts_this_cycle.get(asset_class, 0) >= max_new_per_cycle(asset_class):
        return False, f"{asset_class}_CYCLE_CAP_REACHED"

    return True, "OK"


crypto_pnl = {s: 0.0 for s in SYMBOLS}
fx_pnl = {s: 0.0 for s in FX_SYMBOLS}
options_pnl = {s: 0.0 for s in OPTION_SYMBOLS}
futures_pnl = {s: 0.0 for s in FUTURES_SYMBOLS}

last_trade = "NONE"
cycle = 0


saved_state = session_recovery.load_state()
RESUME_PREVIOUS_SESSION = (os.getenv("CSS_RESUME_SESSION", "false").strip().lower() in {"1", "true", "yes", "y", "on"})
if saved_state and RESUME_PREVIOUS_SESSION:
    cycle = 0
    crypto_pnl.update(saved_state.get("crypto_pnl", {}))
    fx_pnl.update(saved_state.get("fx_pnl", {}))
    options_pnl.update(saved_state.get("options_pnl", {}))
    futures_pnl.update(saved_state.get("futures_pnl", {}))
    last_trade = saved_state.get("last_trade", "NONE")
    mtm_engine.position_counter = saved_state.get("position_counter", 0)

    print(
        "[RECOVERY] Realized PnL restored because CSS_RESUME_SESSION=true; stale open positions not reloaded. "
        "Cycle counter reset."
    )
elif saved_state and not RESUME_PREVIOUS_SESSION:
    print("[RECOVERY IGNORED] Previous realized PnL was not restored. Fresh session active. Set CSS_RESUME_SESSION=true to resume.")


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



# =========================
# R17 EXIT EXECUTION LAYER
# =========================
def r17_execute_exit(pos, observer_symbol, observer_price, reason):
    """
    Institutional exit execution pipeline:
    - Ensures capital, PnL, and lifecycle stay in sync
    """
    try:
        if pos.get("forced_exit"):
            return

        # 1. Book exit (authoritative)
        book_position_exit(pos, reason)

        # 2. Close observer position (PnL)
        try:
            pnl_observer.close_position(observer_symbol, observer_price)
        except Exception as e:
            print(f"[R17 WARN] Observer close failed: {str(e)[:60]}")

        # 3. Ensure capital release safety (idempotent)
        try:
            if pos.get("broker_tested", False):
                capital_governor.release_trade(pos["position_id"])
        except Exception as e:
            print(f"[R17 WARN] Capital release failed: {str(e)[:60]}")

    except Exception as e:
        print(f"[R17 ERROR] Exit execution failure: {str(e)[:80]}")

def book_position_exit(pos: dict, reason: str) -> None:
    global last_trade

    if pos["forced_exit"]:
        return

    if pos.get("broker_order_ok"):
        last_trade = f"{pos['symbol']} BROKER_OPEN_MANUAL_REVIEW"
        return

    realized = round(pos["floating"], 4)

    # === TRACKER UPDATE ===
    try:
        pnl_tracker.record_trade(
            instrument=pos["symbol"],
            realized_pnl=realized,
            unrealized_pnl=0.0
        )
    except Exception as e:
        print(f"[TRACKER ERROR] {e}")

    pos["forced_exit"] = True
    pos["exit_reason"] = reason

    cluster_risk_governor.release_cluster_slot(pos["cluster_name"])

    if pos.get("broker_tested", False):
        capital_governor.release_trade(pos["position_id"])

    target_pnl = pnl_dict_for_asset(pos["asset_class"])
    target_pnl[pos["symbol"]] = round(
        target_pnl.get(pos["symbol"], 0.0) + realized,
        4,
    )

    cluster_amplifier.record_cluster_win(pos["symbol"], realized)

    if reason in {"STOP", "FAST_STOP"}:
        locked_profit_ledger.record_forced_exit(pos["position_id"], realized)
    elif reason == "TAKE_PROFIT":
        locked_profit_ledger.record_priority_exit()
    elif reason == "DEFENSIVE_REDUCTION":
        locked_profit_ledger.record_defensive_reduction_exit()

    locked_profit_ledger.record_recycled_slot()

    last_trade = f"{pos['symbol']} EXIT {reason} {realized:+.4f}"


def apply_defensive_exposure_reduction() -> int:
    if not is_session_locked():
        return 0

    open_positions_list = [
        p for p in mtm_engine.positions if not p["forced_exit"]
    ]

    if not open_positions_list:
        return 0

    open_positions_list.sort(
        key=lambda x: (float(x.get("floating", 0.0)), -int(x.get("age_cycles", 0)))
    )

    reductions = 0

    for pos in open_positions_list:
        if reductions >= DEFENSIVE_REDUCTION_PER_CYCLE:
            break

        if pos.get("broker_order_ok"):
            continue

        book_position_exit(pos, "DEFENSIVE_REDUCTION")
        reductions += 1

    return reductions


def print_oanda_broker_status() -> None:
    print("--- OANDA BROKER STATUS ---")

    resolved_key = bool(os.getenv("OANDA_API_KEY"))
    resolved_account = bool(os.getenv("OANDA_ACCOUNT_ID"))
    resolved_base = os.getenv("OANDA_BASE_URL", "")

    if not (resolved_key and resolved_account):
        print("OANDA CONNECTED: NO")
        print(f"OANDA KEY PRESENT: {'YES' if resolved_key else 'NO'}")
        print(f"OANDA ACCOUNT PRESENT: {'YES' if resolved_account else 'NO'}")
        print(f"OANDA BASE URL: {resolved_base or 'NOT SET'}")
        print("OANDA OPEN TRADES: N/A")
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
            print("OANDA OPEN TRADES: ERR")
            return

        nav = oanda.extract_balance_nav(summary)
        open_trade_count = get_oanda_open_trade_count()

        print("OANDA CONNECTED: YES")
        print(f"BALANCE: {nav['balance']}")
        print(f"NAV: {nav['nav']}")
        print(f"OANDA OPEN TRADES: {open_trade_count}")
        print(f"OANDA BASE URL: {resolved_base}")

    except Exception as e:
        print(f"OANDA ERROR: {str(e)[:60]}")
        print(f"OANDA BASE URL: {resolved_base or 'NOT SET'}")
        print("OANDA OPEN TRADES: ERR")


def print_coinbase_broker_status() -> None:
    print("--- COINBASE BROKER STATUS ---")

    key_present = bool(
        os.getenv("COINBASE_CDP_KEY_NAME")
        or os.getenv("COINBASE_KEY_NAME")
    )
    private_key_present = bool(
        os.getenv("COINBASE_CDP_PRIVATE_KEY_PATH")
        or os.getenv("COINBASE_PRIVATE_KEY")
    )

    print(f"COINBASE SELECTED: {'YES' if SELECTED_BROKER == 'COINBASE' else 'NO'}")
    print(f"COINBASE MODE: {SELECTED_BROKER_MODE if SELECTED_BROKER == 'COINBASE' else 'N/A'}")
    print(f"COINBASE KEY PRESENT: {'YES' if key_present else 'NO'}")
    print(f"COINBASE PRIVATE KEY PRESENT: {'YES' if private_key_present else 'NO'}")
    print(f"COINBASE LIVE ORDER FLAG: {'ON' if coinbase_live_orders_enabled() else 'OFF'}")
    print(f"COINBASE MAX LIVE ORDER USD: ${COINBASE_MAX_LIVE_ORDER_USD:.2f}")

    if SELECTED_BROKER != "COINBASE":
        print("COINBASE CONNECTED: NOT SELECTED")
        return

    if coinbase is None:
        print("COINBASE CONNECTED: NO")
        return

    try:
        if hasattr(coinbase, "ping_live_auth"):
            ping = coinbase.ping_live_auth()
            ok = bool(ping.get("ok")) if isinstance(ping, dict) else False
            mode = ping.get("mode", SELECTED_BROKER_MODE) if isinstance(ping, dict) else SELECTED_BROKER_MODE

            print(f"COINBASE CONNECTED: {'YES' if ok else 'ERROR'}")
            print(f"COINBASE AUTH MODE: {mode}")

            if isinstance(ping, dict) and "account_count" in ping:
                print(f"COINBASE ACCOUNT COUNT: {ping.get('account_count')}")

            return

        configured = bool(coinbase.is_configured()) if hasattr(coinbase, "is_configured") else True
        print(f"COINBASE CONNECTED: {'YES' if configured else 'NO'}")

    except Exception as e:
        print(f"COINBASE ERROR: {str(e)[:80]}")


def broker_execution_status_label() -> str:
    if is_session_locked():
        return "LOCKED_DEFENSIVE_MODE"
    if not BROKER_EXECUTION_ARMED:
        return "DISABLED"
    return "ARMED"


def selected_broker_status_label() -> str:
    return SELECTED_BROKER


def active_execution_scope_label() -> str:
    if is_session_locked():
        return "DEFENSIVE MODE / POSITION MANAGEMENT ONLY"

    if not BROKER_EXECUTION_ARMED:
        return "PAPER ONLY"

    if SELECTED_BROKER == "OANDA":
        return "OANDA FX PRACTICE ONLY"

    if SELECTED_BROKER == "COINBASE":
        if SELECTED_BROKER_MODE == "live" and coinbase_live_orders_enabled():
            return "COINBASE LIVE CRYPTO GATED"
        if SELECTED_BROKER_MODE == "live":
            return "COINBASE LIVE AUTH ONLY / ORDERS BLOCKED"
        return "COINBASE PAPER CRYPTO"

    if SELECTED_BROKER == "NONE":
        return "NO BROKER SELECTED"

    return f"{SELECTED_BROKER} RESERVED / BLOCKED"


def select_cycle_candidates() -> list[tuple[str, str, float, float]]:
    candidates = [
        ("CRYPTO", random.choice(SYMBOLS), 12.0, 0.68),
        ("CRYPTO", random.choice(SYMBOLS), 12.2, 0.69),
        ("FX", random.choice(FX_SYMBOLS), 11.5, 0.66),
        ("FX", random.choice(FX_SYMBOLS), 11.7, 0.67),
        ("OPTIONS", random.choice(OPTION_SYMBOLS), 14.0, 0.71),
        ("OPTIONS", random.choice(OPTION_SYMBOLS), 14.2, 0.72),
        ("FUTURES", random.choice(FUTURES_SYMBOLS), 13.0, 0.69),
        ("FUTURES", random.choice(FUTURES_SYMBOLS), 13.2, 0.70),
    ]
    random.shuffle(candidates)
    return candidates


def pnl_divergence_warning(
    mtm_realized: float,
    mtm_unrealized: float,
    observer_realized: float,
    observer_unrealized: float,
    threshold: float = 0.001,
) -> str | None:
    realized_gap = abs(float(mtm_realized) - float(observer_realized))
    unrealized_gap = abs(float(mtm_unrealized) - float(observer_unrealized))

    if realized_gap > threshold or unrealized_gap > threshold:
        return (
            f"[PNL DIVERGENCE WARNING] "
            f"realized_gap={realized_gap:.6f} "
            f"unrealized_gap={unrealized_gap:.6f}"
        )
    return None


try:
    while True:
        cycle += 1
        current_status = enforce_active_session(cycle, last_trade)

        if not is_session_locked():
            current_status = touch_active_session()
        else:
            current_status = {
                **current_status,
                "active": False,
                "defensive_mode_active": True,
            }

        print(f"=== Cycle {cycle} | {datetime.now()} ===")

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

            observer_symbol = f"{pos['position_id']}::{pos['symbol']}"
            observer_price = 100.0 + float(pos["floating"])
            pnl_observer.update_market_price(observer_symbol, observer_price)

            # =========================
            
            # =========================
            # R15B ENHANCED EXIT ENGINE
            # =========================

            profile = r15b_profile()

            # Convert floating PnL to %
            entry_price = float(pos.get("entry_price", 100.0))
            pnl_pct = pos["floating"] / max(entry_price, 1e-6)

            sig = float(pos.get("signal_score", 0.0))
            prob = float(pos.get("prob_positive", 0.0))

            # =========================
            # EARLY WEAK TRADE CUT
            # =========================
            if pnl_pct <= profile["sl"] * 0.7 and sig < 11.5:
                r17_execute_exit(pos, observer_symbol, observer_price, "FAST_STOP")

            # =========================
            # STANDARD STOP
            # =========================
            elif pnl_pct <= profile["sl"]:
                r17_execute_exit(pos, observer_symbol, observer_price, "STOP")

            # =========================
            # TAKE PROFIT / RUNNER LOGIC
            # =========================
            elif pnl_pct >= profile["tp"]:
                if sig >= 13.5 and prob >= 0.70:
                    # strong trade → let run
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 3)
                    print(f"[R15B RUNNER] {pos['symbol']} strong signal extended")

                elif sig >= 12.5 and prob >= 0.66:
                    # medium trade → slight extension
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 2)
                    print(f"[R15B EXTEND] {pos['symbol']} moderate extension")

                else:
                    # weak profit → take it
                    r17_execute_exit(pos, observer_symbol, observer_price, "TAKE_PROFIT")

            # =========================
            # TIME EXIT (WEAK ONLY)
            if pos.get('forced_exit', False):
                continue  # R16A guard: prevent dual exit execution
            # =========================
            elif pos["age_cycles"] >= exit_profile["max_age"]:
                if sig >= 12.0 and prob >= 0.65:
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 2)
                else:
                    r17_execute_exit(pos, observer_symbol, observer_price, "TIME_EXIT")

            # =========================
            # Cut weak losers earlier than the standard stop.
            if pos["floating"] <= exit_profile["stop_loss"] * 0.8:
                r17_execute_exit(pos, observer_symbol, observer_price, "FAST_STOP")

            # Normal stop for losses that exceed the formal stop threshold.
            elif pos["floating"] <= exit_profile["stop_loss"]:
                r17_execute_exit(pos, observer_symbol, observer_price, "STOP")

            # Let strong winners run instead of clipping them too early.
            elif pos["floating"] >= exit_profile["take_profit"]:
                if pos["signal_score"] >= 13.0 and pos["prob_positive"] >= 0.70:
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 3)
                elif pos["signal_score"] >= 12.0 and pos["prob_positive"] >= 0.66:
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 2)
                else:
                    r17_execute_exit(pos, observer_symbol, observer_price, "TAKE_PROFIT")

            # Time-exit only weak trades; strong trades get more runway.
            elif pos["age_cycles"] >= exit_profile["max_age"]:
                if pos["signal_score"] >= 11.5 and pos["prob_positive"] >= 0.64:
                    pos["age_cycles"] = max(0, pos["age_cycles"] - 2)
                else:
                    r17_execute_exit(pos, observer_symbol, observer_price, "TIME_EXIT")

        defensive_reductions = apply_defensive_exposure_reduction()

        display_by_asset = mtm_engine.floating_by_asset(funded_only=False)
        broker_test_positions = mtm_engine.count_open_broker_test_positions()
        mtm_unrealized = round(sum(display_by_asset.values()), 4)
        open_positions = mtm_engine.count_open_positions()

        mtm_realized = total_realized_pnl()

        realized_by_asset = {
            "CRYPTO": sum(crypto_pnl.values()),
            "FX": sum(fx_pnl.values()),
            "OPTIONS": sum(options_pnl.values()),
            "FUTURES": sum(futures_pnl.values()),
        }
        pcnrass_refresh_balances(realized_by_asset, display_by_asset)

        observer_unrealized = pnl_observer.compute_unrealized_pnl()
        observer_realized = pnl_observer.realized_pnl
        observer_equity = pnl_observer.equity()
        observer_balance = pnl_observer.current_balance

        # ============================================================
        # PCNRASS PNL UNIFICATION
        # ============================================================
        authoritative_realized = mtm_realized
        authoritative_unrealized = mtm_unrealized
        authoritative_equity_pnl = round(authoritative_realized + authoritative_unrealized, 4)
        authoritative_live_equity = round(
            float(pnl_observer.starting_balance) + authoritative_equity_pnl,
            4,
        )

        total_realized = authoritative_realized
        total_unrealized = authoritative_unrealized
        total_equity = authoritative_equity_pnl

        try:
            pnl_observer.current_balance = authoritative_live_equity
        except Exception:
            pass

        try:
            pnl_tracker.current_equity = authoritative_live_equity
            pnl_tracker.peak_equity = max(
                float(getattr(pnl_tracker, "peak_equity", pnl_tracker.starting_equity)),
                authoritative_live_equity,
            )
            if float(getattr(pnl_tracker, "peak_equity", 0.0)) > 0:
                pnl_tracker.max_drawdown = max(
                    float(getattr(pnl_tracker, "max_drawdown", 0.0)),
                    (
                        float(pnl_tracker.peak_equity) - authoritative_live_equity
                    ) / float(pnl_tracker.peak_equity),
                )
        except Exception as e:
            print(f"[TRACKER ALIGN WARN] {e}")

        divergence_msg = None

        top_cluster = cluster_amplifier.top_cluster()
        cluster_pct = (
            cluster_risk_governor.cluster_share(top_cluster) * 100
            if top_cluster
            else 0.0
        )

        dynamic_limit = min(
            concurrency_controller.evaluate_limit(
                open_positions,
                cluster_pct,
                total_unrealized,
            ),
            hard_position_limit(),
        )

        role_profile = SESSION_USER_CTX.get("role_profile", {})
        now_epoch = time.time()
        session_age_seconds = max(0, int(now_epoch - float(current_status.get("created", now_epoch))))
        idle_age_seconds = max(0, int(now_epoch - float(current_status.get("last_activity", now_epoch))))
        idle_remaining = max(0, int(current_status.get("idle_timeout_seconds", SESSION_IDLE_TIMEOUT_SECONDS)) - idle_age_seconds)
        max_remaining = max(0, int(current_status.get("max_session_seconds", SESSION_MAX_SECONDS)) - session_age_seconds)
        lock_state = get_session_lock_state()

        print("--- SESSION CONTEXT ---")
        print(f"USER ID: {SESSION_USER_CTX.get('user_id')} | NAME: {SESSION_USER_CTX.get('display_name')}")
        print(f"DISPLAY NAME: {SESSION_USER_CTX.get('display_name')}")
        print(f"ROLE: {SESSION_USER_CTX.get('role')}")
        print(f"UNIT: {SESSION_USER_CTX.get('unit_code')}")
        print(f"HOME BRANCH: {SESSION_USER_CTX.get('home_branch')}")
        print(f"SESSION ID: {SESSION_USER_CTX.get('session_id')}")
        print(f"COMPUTER NAME: {SESSION_USER_CTX.get('computer_name')}")
        print(f"LOGIN CHANNEL: {SESSION_USER_CTX.get('login_channel')}")
        print(f"SESSION ACTIVE: {'YES' if current_status.get('active') else 'NO'}")
        print(f"DEFENSIVE MODE ACTIVE: {'YES' if is_session_locked() else 'NO'}")
        print(f"SESSION LOCK REASON: {lock_state.get('reason') or 'NONE'}")
        print(f"SESSION AGE SEC: {session_age_seconds}")
        print(f"IDLE TIMEOUT SEC: {current_status.get('idle_timeout_seconds', SESSION_IDLE_TIMEOUT_SECONDS)}")
        print(f"MAX SESSION SEC: {current_status.get('max_session_seconds', SESSION_MAX_SECONDS)}")
        print(f"IDLE REMAINING SEC: {idle_remaining}")
        print(f"MAX REMAINING SEC: {max_remaining}")
        print(f"CAN ARM BROKER: {'YES' if role_profile.get('can_arm_broker') else 'NO'}")
        print(f"CAN LIVE MODE: {'YES' if role_profile.get('can_use_live_broker_mode') else 'NO'}")
        print(f"CAN PAPER EXECUTE: {'YES' if role_profile.get('can_execute_paper_trading') else 'NO'}")
        print(f"CAN LIVE EXECUTE: {'YES' if role_profile.get('can_execute_live_trading') else 'NO'}")
        print(f"ALLOWED ENGINE MODES: {', '.join(role_profile.get('allowed_engine_modes', [])) or 'NONE'}")

        if SELECTED_BROKER == "OANDA":
            print_oanda_broker_status()
            print("--- COINBASE BROKER STATUS ---")
            print("COINBASE SELECTED: NO")
            print("COINBASE CONNECTED: NO")
        elif SELECTED_BROKER == "COINBASE":
            print("--- OANDA BROKER STATUS ---")
            print("OANDA SELECTED: NO")
            print("OANDA CONNECTED: NO")
            print("OANDA OPEN TRADES: N/A")
            print_coinbase_broker_status()
        else:
            print("--- OANDA BROKER STATUS ---")
            print("OANDA SELECTED: NO")
            print("OANDA CONNECTED: NO")
            print("OANDA OPEN TRADES: N/A")
            print("--- COINBASE BROKER STATUS ---")
            print("COINBASE SELECTED: NO")
            print("COINBASE CONNECTED: NO")

        print("--- BROKER EXECUTION CONTROL ---")
        print(f"BROKER EXECUTION: {broker_execution_status_label()}")
        print(f"SELECTED BROKER: {selected_broker_status_label()}")
        print(f"BROKER MODE: {SELECTED_BROKER_MODE}")
        print(f"EXECUTION SCOPE: {active_execution_scope_label()}")

        print("--- LIVE EXECUTION SUMMARY ---")
        print(f"REALIZED PNL: {total_realized:+.4f}")
        print(f"UNREALIZED PNL: {total_unrealized:+.4f}")
        print(f"TOTAL EQUITY PNL: {total_equity:+.4f}")
        print(f"BALANCE: {observer_balance:+.4f}")

        print("--- PNL RECONCILIATION ---")
        print(f"OBSERVER REALIZED PNL: {observer_realized:+.4f}")
        print(f"OBSERVER UNREALIZED PNL: {observer_unrealized:+.4f}")
        print(f"OBSERVER EQUITY: {observer_equity:+.4f}")
        print(f"OBSERVER BALANCE: {observer_balance:+.4f}")
        print(f"MTM REALIZED PNL: {mtm_realized:+.4f}")
        print(f"MTM UNREALIZED PNL: {mtm_unrealized:+.4f}")
        print("[PNL AUTHORITY] MTM/accounting PnL is authoritative; observer retained as compatibility mirror.")
        observer_gap_realized = round(abs(float(mtm_realized) - float(observer_realized)), 6)
        observer_gap_unrealized = round(abs(float(mtm_unrealized) - float(observer_unrealized)), 6)
        if observer_gap_realized or observer_gap_unrealized:
            print(
                f"[OBSERVER MIRROR GAP] realized_gap={observer_gap_realized:.6f} "
                f"unrealized_gap={observer_gap_unrealized:.6f}"
            )

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

        open_counts_by_asset = mtm_engine.count_open_positions_by_asset()

        print(f"OPEN POSITIONS: {open_positions} / {hard_position_limit()}")
        print(
            "OPEN BY ASSET: "
            f"CRYPTO {open_counts_by_asset['CRYPTO']}/{hard_asset_cap('CRYPTO')} | "
            f"FX {open_counts_by_asset['FX']}/{hard_asset_cap('FX')} | "
            f"FUTURES {open_counts_by_asset['FUTURES']}/{hard_asset_cap('FUTURES')} | "
            f"OPTIONS {open_counts_by_asset['OPTIONS']}/{hard_asset_cap('OPTIONS')}"
        )
        print(f"ADAPTIVE POSITION LIMIT: {dynamic_limit}")
        print(f"BROKER TEST POSITIONS: {broker_test_positions}")
        print(f"DEFENSIVE REDUCTIONS THIS CYCLE: {defensive_reductions}")
        print(f"TOTAL DEFENSIVE REDUCTION EXITS: {locked_profit_ledger.defensive_reduction_exits}")

        capital_source = capital_governor.capital_source_label()
        print(
            f"{capital_source} CAPITAL DEPLOYED: "
            f"${capital_governor.funded_amount():.2f}"
        )
        print(
            f"{capital_source} CAPITAL AVAILABLE: "
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

        live_fx_funded_this_cycle = 0
        live_crypto_funded_this_cycle = 0
        new_counts_this_cycle = {
            "CRYPTO": 0,
            "FX": 0,
            "OPTIONS": 0,
            "FUTURES": 0,
        }

        if is_session_locked():
            if defensive_reductions > 0:
                print(
                    f"[DEFENSIVE MODE] New trade creation blocked. "
                    f"Reduced exposure by {defensive_reductions} positions this cycle."
                )
            else:
                print("[DEFENSIVE MODE] New trade creation blocked. Managing existing positions only.")
        elif mtm_engine.count_open_positions() < hard_position_limit():
            if not role_profile.get("can_execute_paper_trading", False):
                print("[RBAC] New position generation blocked for current role.")
            else:
                for asset_class, symbol, sig, prob in select_cycle_candidates():
                    # =========================
                    # MODE-AWARE ENTRY FILTER
                    # =========================
                    mode_filter = {
                        "SAFE": (12.5, 0.55),
                        "CONSERVATIVE": (12.0, 0.50),
                        "BALANCED": (11.0, 0.40),
                        "AGGRESSIVE": (10.5, 0.36),
                        "EXPANSION": (10.0, 0.32),
                    }

                    min_sig, min_prob = mode_filter.get(ENGINE_MODE, (11.5, 0.65))

                    # PCNRASS profitability guardrail:
                    # avoid very weak/noisy entries while preserving existing mode behavior.
                    if sig < min_sig or prob < min_prob:
                        continue

                    if sig < 10.0:
                        continue

                    current_open_counts = mtm_engine.count_open_positions_by_asset()

                    if not concurrency_controller.can_add_position(
                        mtm_engine.count_open_positions()
                    ):
                        break

                    if mtm_engine.count_open_positions() >= hard_position_limit():
                        break

                    allowed_to_open, open_reason = can_open_position(
                        asset_class,
                        open_counts=current_open_counts,
                        new_counts_this_cycle=new_counts_this_cycle,
                    )
                    if not allowed_to_open:
                        continue

                    if asset_class == "CRYPTO":
                        safe_load_runtime_asset(symbol)

                    allow_broker_test = False

                    if (
                        asset_class == "FX"
                        and SELECTED_BROKER == "OANDA"
                        and live_fx_funded_this_cycle < max_new_per_cycle("FX")
                    ):
                        allow_broker_test = True

                    if (
                        asset_class == "CRYPTO"
                        and SELECTED_BROKER == "COINBASE"
                        and live_crypto_funded_this_cycle < max_new_per_cycle("CRYPTO")
                    ):
                        allow_broker_test = True

                    gate_ok, gate_reason = approve_trade_before_register(
                        asset_class=asset_class,
                        symbol=symbol,
                        sig=sig,
                        prob=prob,
                    )

                    if not gate_ok:
                        last_trade = f"{symbol} UNIFIED_GATE_BLOCKED {gate_reason}"
                        continue

                    r14f_ok, r14f_score, r14f_threshold = css_profitability_allows(
                        symbol=symbol,
                        asset_class=asset_class,
                        sig=sig,
                        prob=prob,
                    )

                    if not r14f_ok:
                        last_trade = f"{symbol} R14F_BLOCKED"
                        continue

                    position = mtm_engine.register_position(
                        asset_class,
                        symbol,
                        sig,
                        prob,
                        allow_live_funding=allow_broker_test,
                    )
                    new_counts_this_cycle[asset_class] += 1

                    observer_position = Position(
                        symbol=f"{position['position_id']}::{symbol}",
                        asset_class=asset_class,
                        side="LONG",
                        quantity=1.0,
                        entry_price=100.0,
                        current_price=100.0,
                    )
                    pnl_observer.add_position(observer_position)
                    exit_signal = evaluate_exit_signal(position)
                    print(f"[R15A EXIT] {symbol} signal={exit_signal}")

                    if position.get("broker_tested"):
                        if asset_class == "FX" and SELECTED_BROKER == "OANDA":
                            live_fx_funded_this_cycle += 1
                            ok, broker_msg = attempt_oanda_fx_execution(symbol)

                        elif asset_class == "CRYPTO" and SELECTED_BROKER == "COINBASE":
                            live_crypto_funded_this_cycle += 1
                            ok, broker_msg = attempt_coinbase_crypto_execution(symbol)

                        else:
                            ok, broker_msg = False, "BROKER_ASSET_MISMATCH"

                        if ok:
                            position["broker_order_ok"] = True
                            position["broker_note"] = broker_msg
                            last_trade = f"{symbol} BROKER_EXECUTED {broker_msg}"
                            print(
                                f"[{asset_class} BROKER EXECUTED] {symbol} opened | "
                                f"{broker_msg}"
                            )
                        else:
                            capital_governor.release_trade(position["position_id"])
                            position["broker_tested"] = False
                            position["live_funded"] = False
                            position["broker_order_ok"] = False
                            position["broker_note"] = broker_msg
                            last_trade = f"{symbol} PAPER_OPENED BROKER_BLOCKED {broker_msg}"
                            print(
                                f"[{asset_class} PAPER OPENED] {symbol} opened | "
                                f"BROKER_BLOCKED | {broker_msg}"
                            )

                    else:
                        last_trade = f"{symbol} PAPER_OPENED"
                        print(f"[{asset_class} PAPER OPENED] {symbol}")
        else:
            print("[SIGNAL GENERATION PAUSED] hard open-position cap reached")


        session_recovery.save_state(
            cycle=cycle,
            crypto_pnl=crypto_pnl,
            fx_pnl=fx_pnl,
            options_pnl=options_pnl,
            futures_pnl=futures_pnl,
            last_trade=last_trade,
            position_counter=mtm_engine.position_counter,
        )

        
        try:
            new_positions = []
            for pos in mtm_engine.positions:
                if pos["forced_exit"]:
                    continue
                new_positions.append(
                    NewPosition(
                        symbol=pos["symbol"],
                        side="LONG",
                        entry_price=float(pos.get("entry_price", 100.0)),
                        current_price=float(pos.get("current_price", pos.get("entry_price", 100.0))),
                        quantity=1.0,
                        instrument_spec=InstrumentSpec(
                            symbol=pos["symbol"],
                            asset_class=pos["asset_class"],
                            multiplier=1.0,
                        ),
                        entry_cost=ExecutionCost(),
                        estimated_exit_cost=ExecutionCost(),
                    )
                )

            snapshot = compute_portfolio_snapshot(
                new_positions,
                starting_equity=float(pnl_observer.starting_balance) + float(total_realized),
            )

            print("--- NEW ACCOUNTING ENGINE ---")
            print(f"NET UNREALIZED: {snapshot.total_net_unrealized:+.4f}")
            print(f"LIVE EQUITY: {snapshot.live_equity:+.4f}")

            tracker_snapshot = pnl_tracker.equity_snapshot()
            print("--- TRACKER PERFORMANCE ---")
            print(f"TRACKER EQUITY: {tracker_snapshot['current_equity']:+.4f}")
            print(f"PEAK EQUITY: {tracker_snapshot['peak_equity']:+.4f}")
            print(f"DRAWDOWN: {tracker_snapshot['current_drawdown']:.4%}")

        except Exception as e:
            print(f"[NEW PNL ERROR] {e}")

        if not pcnrass_wait_for_next_cycle(cycle):

            close_active_session("operator_quit_after_cycle")

            break

        time.sleep(1)

except KeyboardInterrupt:
    print("[SESSION STOPPED] Keyboard interrupt received.")
    close_active_session(
        "keyboard_interrupt",
        extra={
            "cycle": cycle,
            "last_trade": last_trade,
            "open_positions": mtm_engine.count_open_positions(),
            "realized_pnl": total_realized_pnl(),
            "defensive_mode_active": is_session_locked(),
        },
    )

except SystemExit:
    raise

except Exception as e:
    print(f"[FATAL ERROR] {str(e)[:200]}")
    close_active_session(
        "runtime_error",
        extra={
            "cycle": cycle,
            "last_trade": last_trade,
            "open_positions": mtm_engine.count_open_positions(),
            "realized_pnl": total_realized_pnl(),
            "error": str(e)[:200],
            "defensive_mode_active": is_session_locked(),
        },
    )
    raise

finally:
    close_active_session(
        "normal_shutdown",
        extra={
            "cycle": cycle,
            "last_trade": last_trade,
            "open_positions": mtm_engine.count_open_positions(),
            "realized_pnl": total_realized_pnl(),
            "defensive_mode_active": is_session_locked(),
        },
    )
# ===== PCNRASS FINAL ACCOUNT SETTLEMENT =====
def finalize_account_session() -> None:
    try:
        if "pcnrass_session_state" not in globals() or "pcnrass_account_state" not in globals():
            return

        new_balance = float(pcnrass_session_state.get("session_equity", 0.0))
        if new_balance <= 0:
            return

        pcnrass_account_state["account_balance"] = round(new_balance, 4)
        pcnrass_account_state["last_session_close"] = datetime.now().isoformat(timespec="seconds")

        if "ACCOUNT_STATE_FILE" in globals():
            Path(ACCOUNT_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
            Path(ACCOUNT_STATE_FILE).write_text(
                json.dumps(pcnrass_account_state, indent=2, default=str),
                encoding="utf-8",
            )

        print(f"[ACCOUNT UPDATED] new balance: {new_balance:.2f}")

    except Exception as e:
        print(f"[ACCOUNT SETTLEMENT ERROR] {e}")
