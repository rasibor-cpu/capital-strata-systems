from __future__ import annotations

import contextlib
import io
import json
import os
import random
import socket
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from backend.app.pnl.pnl_engine import Portfolio, Position

from backend.core.session_state import get_session_lock_state, is_session_locked, lock_session
from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.app.brokers.oanda_adapter import OandaAdapter
from backend.app.brokers.broker_bootstrap import initialize_broker
from backend.app.brokers.coinbase_live_order_gate import CoinbaseLiveOrderGate
from backend.app.brokers.broker_gate_audit import BrokerGateAuditLogger
from backend.app.security.auth_gate import await_login_ready_state
from backend.security.access_control import AccessControl
from backend.security.audit_ledger import AuditLedger
from backend.security.session_manager import SessionManager


ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

STATE_FILE = ARTIFACTS_DIR / "css_session_recovery.json"

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
FX_LIVE_UNITS = 1
COINBASE_TEST_ORDER_USD = float(os.getenv("COINBASE_TEST_ORDER_USD", "1.00") or 1.00)
COINBASE_MAX_LIVE_ORDER_USD = float(os.getenv("COINBASE_MAX_LIVE_ORDER_USD", "1.00") or 1.00)

SESSION_IDLE_TIMEOUT_SECONDS = int(os.getenv("CSS_SESSION_IDLE_TIMEOUT_SECONDS", "3600") or 3600)
SESSION_MAX_SECONDS = int(os.getenv("CSS_SESSION_MAX_SECONDS", "28800") or 28800)

MAX_PAPER_OPEN_POSITIONS = 40
MAX_OPEN_PER_CYCLE = 4
DEFENSIVE_REDUCTION_PER_CYCLE = 2

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

audit_ledger = AuditLedger()
session_manager = SessionManager(
    idle_timeout_seconds=SESSION_IDLE_TIMEOUT_SECONDS,
    max_session_seconds=SESSION_MAX_SECONDS,
)
access_control = AccessControl()
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
        session = session_manager.create_session(
            username=str(user_ctx.get("user_id")),
            role=str(user_ctx.get("role")),
            idle_timeout_seconds=SESSION_IDLE_TIMEOUT_SECONDS,
            max_session_seconds=SESSION_MAX_SECONDS,
        )
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
        origin = runtime_origin_context()
        audit_ledger.record(
            "login_cancelled",
            "UNKNOWN",
            {
                "reason": "keyboard_interrupt",
                **origin,
            },
        )
        print("\n[AUTH CANCELLED] Startup aborted by user.")
        raise SystemExit(1)

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

    print("\n=== CSS BROKER EXECUTION ARMING ===")
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

    print("\n=== CSS BROKER SELECTION ===")
    print("1. NONE / ARMED BUT NO BROKER")
    print("2. OANDA - FX practice execution")
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
        if not role_profile.get("can_use_paper_broker_mode", False):
            print(f"[RBAC] OANDA practice mode denied for role {role}.")
            record_rbac_event(
                "broker_mode_denied",
                SESSION_USER_CTX,
                {
                    "selected_broker": "OANDA",
                    "selected_broker_mode": "paper",
                    "reason": "role_cannot_use_paper_broker_mode",
                },
            )
            return False, "NONE", "paper"

        record_rbac_event(
            "broker_selected",
            SESSION_USER_CTX,
            {
                "selected_broker": "OANDA",
                "selected_broker_mode": "paper",
            },
        )
        print("[BROKER EXECUTION ARMED] Selected broker: OANDA / FX practice only")
        return True, "OANDA", "paper"

    if selected == "COINBASE":
        print("\n=== COINBASE MODE ===")
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

    print("\n=== CSS ENGINE MODE SELECTOR ===")
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

    session_id = SESSION_USER_CTX.get("session_id")
    if session_id:
        session_manager.destroy_session(str(session_id), reason=reason)

    SESSION_CLOSED = True

SESSION_USER_CTX = authenticate_startup_user()

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
    Controlled test allocation governor.

    These values are internal CSS test allocations. They are not real broker
    balances unless a broker order is separately allowed and executed.
    """

    def __init__(self) -> None:
        self.paper_mode = False
        self.simulated_capital_pool = 200.00
        self.max_capital_per_trade = 25.00
        self.max_broker_test_positions = 5
        self.active_test_allocations: dict[str, float] = {}

    def available_capital(self) -> float:
        allocated = sum(self.active_test_allocations.values())
        base_capital = float(getattr(pnl_observer, "current_balance", self.simulated_capital_pool))
        return round(base_capital - allocated, 4)

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

    def set_paper_mode(self) -> None:
        self.paper_mode = True


capital_governor = CapitalDeploymentGovernor()

# Phase 1 PnL observer only
pnl_observer = Portfolio(
    starting_balance=capital_governor.simulated_capital_pool,
    current_balance=capital_governor.simulated_capital_pool,
)


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

        position = {
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
            "broker_tested": broker_tested,
            "live_funded": broker_tested,
            "broker_order_ok": False,            "broker_note": "NO_BROKER_ORDER",
            "session_user_id": SESSION_USER_CTX.get("user_id"),
            "session_role": SESSION_USER_CTX.get("role"),
            "session_id": SESSION_USER_CTX.get("session_id"),
        }

        self.positions.append(position)
        return position

    def count_open_positions(self) -> int:
        return sum(1 for p in self.positions if not p["forced_exit"])

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

    if pos.get("broker_order_ok"):
        last_trade = f"{pos['symbol']} BROKER_OPEN_MANUAL_REVIEW"
        return

    realized = round(pos["floating"], 4)

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

    if reason == "STOP":
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
    print("\n--- OANDA BROKER STATUS ---")

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
    print("\n--- COINBASE BROKER STATUS ---")

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


def select_four_candidates() -> list[tuple[str, str, float, float]]:
    return [
        ("CRYPTO", random.choice(SYMBOLS), 12.0, 0.68),
        ("FX", random.choice(FX_SYMBOLS), 11.5, 0.66),
        ("OPTIONS", random.choice(OPTION_SYMBOLS), 14.0, 0.71),
        ("FUTURES", random.choice(FUTURES_SYMBOLS), 13.0, 0.69),
    ]


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

        print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

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

            if pos["floating"] <= exit_profile["stop_loss"]:
                book_position_exit(pos, "STOP")
                pnl_observer.close_position(observer_symbol, observer_price)
            elif pos["floating"] >= exit_profile["take_profit"]:
                book_position_exit(pos, "TAKE_PROFIT")
                pnl_observer.close_position(observer_symbol, observer_price)
            elif pos["age_cycles"] >= exit_profile["max_age"]:
                book_position_exit(pos, "TIME_EXIT")
                pnl_observer.close_position(observer_symbol, observer_price)

        defensive_reductions = apply_defensive_exposure_reduction()

        display_by_asset = mtm_engine.floating_by_asset(funded_only=False)
        broker_test_positions = mtm_engine.count_open_broker_test_positions()
        mtm_unrealized = round(sum(display_by_asset.values()), 4)
        open_positions = mtm_engine.count_open_positions()

        mtm_realized = total_realized_pnl()

        observer_unrealized = pnl_observer.compute_unrealized_pnl()
        observer_realized = pnl_observer.realized_pnl
        observer_equity = pnl_observer.equity()
        observer_balance = pnl_observer.current_balance

        total_realized = observer_realized
        total_unrealized = observer_unrealized
        total_equity = observer_equity - pnl_observer.starting_balance

        divergence_msg = pnl_divergence_warning(
            mtm_realized=mtm_realized,
            mtm_unrealized=mtm_unrealized,
            observer_realized=observer_realized,
            observer_unrealized=observer_unrealized,
        )

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

        role_profile = SESSION_USER_CTX.get("role_profile", {})
        now_epoch = time.time()
        session_age_seconds = max(0, int(now_epoch - float(current_status.get("created", now_epoch))))
        idle_age_seconds = max(0, int(now_epoch - float(current_status.get("last_activity", now_epoch))))
        idle_remaining = max(0, int(current_status.get("idle_timeout_seconds", SESSION_IDLE_TIMEOUT_SECONDS)) - idle_age_seconds)
        max_remaining = max(0, int(current_status.get("max_session_seconds", SESSION_MAX_SECONDS)) - session_age_seconds)
        lock_state = get_session_lock_state()

        print("\n--- SESSION CONTEXT ---")
        print(f"USER ID: {SESSION_USER_CTX.get('user_id')}")
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

        print_oanda_broker_status()
        print_coinbase_broker_status()

        print("\n--- BROKER EXECUTION CONTROL ---")
        print(f"BROKER EXECUTION: {broker_execution_status_label()}")
        print(f"SELECTED BROKER: {selected_broker_status_label()}")
        print(f"BROKER MODE: {SELECTED_BROKER_MODE}")
        print(f"EXECUTION SCOPE: {active_execution_scope_label()}")

        print("\n--- LIVE EXECUTION SUMMARY ---")
        print(f"REALIZED PNL: {total_realized:+.4f}")
        print(f"UNREALIZED PNL: {total_unrealized:+.4f}")
        print(f"TOTAL EQUITY PNL: {total_equity:+.4f}")
        print(f"BALANCE: {observer_balance:+.4f}")

        print("\n--- PNL RECONCILIATION ---")
        print(f"OBSERVER REALIZED PNL: {observer_realized:+.4f}")
        print(f"OBSERVER UNREALIZED PNL: {observer_unrealized:+.4f}")
        print(f"OBSERVER EQUITY: {observer_equity:+.4f}")
        print(f"OBSERVER BALANCE: {observer_balance:+.4f}")
        print(f"MTM REALIZED PNL: {mtm_realized:+.4f}")
        print(f"MTM UNREALIZED PNL: {mtm_unrealized:+.4f}")
        if divergence_msg:
            print(divergence_msg)

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
        print(f"BROKER TEST POSITIONS: {broker_test_positions}")
        print(f"DEFENSIVE REDUCTIONS THIS CYCLE: {defensive_reductions}")
        print(f"TOTAL DEFENSIVE REDUCTION EXITS: {locked_profit_ledger.defensive_reduction_exits}")

        print(
            f"SIMULATED CAPITAL DEPLOYED: "
            f"${capital_governor.funded_amount():.2f}"
        )
        print(
            f"SIMULATED CAPITAL AVAILABLE: "
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

        if is_session_locked():
            if defensive_reductions > 0:
                print(
                    f"[DEFENSIVE MODE] New trade creation blocked. "
                    f"Reduced exposure by {defensive_reductions} positions this cycle."
                )
            else:
                print("[DEFENSIVE MODE] New trade creation blocked. Managing existing positions only.")
        elif mtm_engine.count_open_positions() < MAX_PAPER_OPEN_POSITIONS:
            if not role_profile.get("can_execute_paper_trading", False):
                print("[RBAC] New position generation blocked for current role.")
            else:
                for asset_class, symbol, sig, prob in select_four_candidates():
                    if not concurrency_controller.can_add_position(
                        mtm_engine.count_open_positions()
                    ):
                        break

                    if mtm_engine.count_open_positions() >= MAX_PAPER_OPEN_POSITIONS:
                        break

                    if asset_class == "CRYPTO":
                        safe_load_runtime_asset(symbol)

                    allow_broker_test = False

                    if (
                        asset_class == "FX"
                        and SELECTED_BROKER == "OANDA"
                        and live_fx_funded_this_cycle < 1
                    ):
                        allow_broker_test = True

                    if (
                        asset_class == "CRYPTO"
                        and SELECTED_BROKER == "COINBASE"
                        and live_crypto_funded_this_cycle < 1
                    ):
                        allow_broker_test = True

                    position = mtm_engine.register_position(
                        asset_class,
                        symbol,
                        sig,
                        prob,
                        allow_live_funding=allow_broker_test,
                    )

                    observer_position = Position(
                        symbol=f"{position['position_id']}::{symbol}",
                        asset_class=asset_class,
                        side="LONG",
                        quantity=1.0,
                        entry_price=100.0,
                        current_price=100.0,
                    )
                    pnl_observer.add_position(observer_position)

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
            print("[SIGNAL GENERATION PAUSED] paper open-position cap reached")

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

except KeyboardInterrupt:
    print("\n[SESSION STOPPED] Keyboard interrupt received.")
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