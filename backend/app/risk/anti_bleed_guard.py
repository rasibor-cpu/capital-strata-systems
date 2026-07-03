from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional


STATE_FILE = os.path.join("artifacts", "anti_bleed_state.json")
LIVE_LIKE_ENVIRONMENTS = {"prod", "production", "live", "staging", "uat"}
DEV_TEST_ENVIRONMENTS = {"dev", "development", "local", "test", "testing", "ci"}


class AntiBleedGuardConfigurationError(RuntimeError):
    """Raised when AntiBleedGuard is configured unsafely."""


def _utc_now_compat() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _dev_force_allow_permitted() -> bool:
    env_values = {
        os.getenv("CSS_ENV", ""),
        os.getenv("APP_ENV", ""),
        os.getenv("ENV", ""),
        os.getenv("PYTHON_ENV", ""),
    }
    normalized = {value.strip().lower() for value in env_values if value}
    if normalized & LIVE_LIKE_ENVIRONMENTS:
        return False
    if normalized & DEV_TEST_ENVIRONMENTS:
        return True
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


class AntiBleedGuard:
    """
    CSS Anti-Bleed Cost-Aware Trade Guard

    Prevents:
    - Low edge trades
    - Fee bleed
    - Rapid buy/sell loops
    - Micro trade inefficiency
    """

    def __init__(
        self,
        minimum_required_net_edge_bps: float = 25.0,
        minimum_profitable_trade_size: float = 50.0,
        cooldown_minutes: int = 10,
        max_trades_per_symbol_per_cycle: int = 1,
        dev_force_allow: bool = False,
        state_file: str = STATE_FILE,
    ):
        self.minimum_required_net_edge_bps = minimum_required_net_edge_bps
        self.minimum_profitable_trade_size = minimum_profitable_trade_size
        self.cooldown_minutes = cooldown_minutes
        self.max_trades_per_symbol_per_cycle = max_trades_per_symbol_per_cycle
        if dev_force_allow and not _dev_force_allow_permitted():
            raise AntiBleedGuardConfigurationError(
                "dev_force_allow=True is restricted to explicit development/test environments"
            )
        self.dev_force_allow = dev_force_allow
        self.state_file = state_file

        self.state = self._load_state()

    # -----------------------------
    # PUBLIC ENTRY
    # -----------------------------
    def evaluate(
        self,
        symbol: str,
        trade_size: float,
        expected_move_bps: float,
        fee_bps: float,
        spread_bps: float,
        slippage_bps: float,
        side: str = "UNKNOWN",
    ) -> Dict[str, Any]:

        total_cost_bps = fee_bps + spread_bps + slippage_bps
        net_edge_bps = expected_move_bps - total_cost_bps

        now = _utc_now_compat()

        cooldown_active, cooldown_until = self._is_in_cooldown(symbol, now)

        decision = {
            "approved": True,
            "reason": "approved",
            "symbol": symbol,
            "side": side,
            "trade_size": trade_size,
            "expected_move_bps": expected_move_bps,
            "total_cost_bps": total_cost_bps,
            "net_edge_bps": net_edge_bps,
            "minimum_required_net_edge_bps": self.minimum_required_net_edge_bps,
            "cooldown_active": cooldown_active,
            "cooldown_until": cooldown_until,
            "timestamp": now.isoformat(),
        }

        # -----------------------------
        # REJECTION RULES
        # -----------------------------

        if expected_move_bps <= total_cost_bps:
            return self._reject(decision, "expected_move_below_cost")

        if net_edge_bps < self.minimum_required_net_edge_bps:
            return self._reject(decision, "insufficient_net_edge")

        if trade_size < self.minimum_profitable_trade_size:
            return self._reject(decision, "trade_size_too_small")

        if cooldown_active:
            return self._reject(decision, "cooldown_active")

        # -----------------------------
        # APPROVED → UPDATE STATE
        # -----------------------------
        self._update_trade_state(symbol, now)

        return decision

    # -----------------------------
    # INTERNAL HELPERS
    # -----------------------------

    def _reject(self, decision: Dict[str, Any], reason: str) -> Dict[str, Any]:
        decision["approved"] = False
        decision["reason"] = reason

        self._log_rejection(decision)

        if self.dev_force_allow:
            decision["approved"] = True
            decision["reason"] = f"DEV_OVERRIDE:{reason}"

        return decision

    def _is_in_cooldown(
        self,
        symbol: str,
        now: datetime,
    ) -> tuple[bool, Optional[str]]:

        symbol_state = self.state.get(symbol, {})
        cooldown_until_str = symbol_state.get("cooldown_until")

        if not cooldown_until_str:
            return False, None

        cooldown_until = datetime.fromisoformat(cooldown_until_str)

        if now < cooldown_until:
            return True, cooldown_until_str

        return False, cooldown_until_str

    def _update_trade_state(self, symbol: str, now: datetime):

        cooldown_until = now + timedelta(minutes=self.cooldown_minutes)

        self.state[symbol] = {
            "last_trade_time": now.isoformat(),
            "cooldown_until": cooldown_until.isoformat(),
        }

        self._save_state()

    # -----------------------------
    # STATE MANAGEMENT
    # -----------------------------

    def _load_state(self) -> Dict[str, Any]:
        if not os.path.exists(self.state_file):
            return {}

        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self):
        state_dir = os.path.dirname(self.state_file)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)

        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    # -----------------------------
    # LOGGING
    # -----------------------------

    def _log_rejection(self, decision: Dict[str, Any]):

        log_line = (
            f"ANTI_BLEED_REJECT | "
            f"symbol={decision['symbol']} | "
            f"side={decision['side']} | "
            f"size={decision['trade_size']} | "
            f"expected={decision['expected_move_bps']}bps | "
            f"cost={decision['total_cost_bps']}bps | "
            f"net={decision['net_edge_bps']}bps | "
            f"reason={decision['reason']} | "
            f"time={decision['timestamp']}"
        )

        print(log_line)
