from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


STATE_FILE = os.path.join("artifacts", "anti_bleed_state.json")


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
    ):
        self.minimum_required_net_edge_bps = minimum_required_net_edge_bps
        self.minimum_profitable_trade_size = minimum_profitable_trade_size
        self.cooldown_minutes = cooldown_minutes
        self.max_trades_per_symbol_per_cycle = max_trades_per_symbol_per_cycle
        self.dev_force_allow = dev_force_allow

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

        now = datetime.utcnow()

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
        if not os.path.exists(STATE_FILE):
            return {}

        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self):
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

        with open(STATE_FILE, "w") as f:
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
