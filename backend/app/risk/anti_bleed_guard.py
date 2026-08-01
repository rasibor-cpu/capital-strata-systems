from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from backend.app.risk.anti_bleed_policy import (
    STANDARD,
    AntiBleedPolicy,
    AntiBleedPolicyError,
)


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


def _policy_from_legacy_kwargs(
    *,
    base: AntiBleedPolicy,
    minimum_required_net_edge_bps: Optional[float],
    minimum_profitable_trade_size: Optional[float],
    cooldown_minutes: Optional[int],
    max_trades_per_symbol_per_cycle: Optional[int],
    allow_dev_override: Optional[bool],
) -> AntiBleedPolicy:
    """Build an immutable policy for test/legacy constructors without mutating registry profiles."""
    return AntiBleedPolicy(
        name=f"{base.name}_CUSTOM" if base.name else "CUSTOM",
        policy_id=f"{base.policy_id}_CUSTOM" if base.policy_id else "CUSTOM",
        policy_version=base.policy_version,
        minimum_profitable_trade_size=(
            float(minimum_profitable_trade_size)
            if minimum_profitable_trade_size is not None
            else base.minimum_profitable_trade_size
        ),
        minimum_required_net_edge_bps=(
            float(minimum_required_net_edge_bps)
            if minimum_required_net_edge_bps is not None
            else base.minimum_required_net_edge_bps
        ),
        cooldown_minutes=(
            int(cooldown_minutes) if cooldown_minutes is not None else base.cooldown_minutes
        ),
        maximum_symbol_frequency=(
            int(max_trades_per_symbol_per_cycle)
            if max_trades_per_symbol_per_cycle is not None
            else base.maximum_symbol_frequency
        ),
        require_complete_microstructure_inputs=base.require_complete_microstructure_inputs,
        allow_dev_override=(
            bool(allow_dev_override) if allow_dev_override is not None else base.allow_dev_override
        ),
    )


class AntiBleedGuard:
    """
    CSS Anti-Bleed Cost-Aware Trade Guard

    Prevents:
    - Low edge trades
    - Fee bleed
    - Rapid buy/sell loops
    - Micro trade inefficiency

    Thresholds come from an immutable AntiBleedPolicy (Phase 184A).
    Evaluation order and reject reason strings are unchanged.
    """

    def __init__(
        self,
        policy: Optional[AntiBleedPolicy] = None,
        *,
        minimum_required_net_edge_bps: Optional[float] = None,
        minimum_profitable_trade_size: Optional[float] = None,
        cooldown_minutes: Optional[int] = None,
        max_trades_per_symbol_per_cycle: Optional[int] = None,
        dev_force_allow: Optional[bool] = None,
        state_file: str = STATE_FILE,
    ):
        base = policy if policy is not None else STANDARD
        if not isinstance(base, AntiBleedPolicy):
            raise AntiBleedPolicyError("policy must be an AntiBleedPolicy instance")

        legacy_override = any(
            value is not None
            for value in (
                minimum_required_net_edge_bps,
                minimum_profitable_trade_size,
                cooldown_minutes,
                max_trades_per_symbol_per_cycle,
                dev_force_allow,
            )
        )
        if legacy_override:
            active = _policy_from_legacy_kwargs(
                base=base,
                minimum_required_net_edge_bps=minimum_required_net_edge_bps,
                minimum_profitable_trade_size=minimum_profitable_trade_size,
                cooldown_minutes=cooldown_minutes,
                max_trades_per_symbol_per_cycle=max_trades_per_symbol_per_cycle,
                allow_dev_override=dev_force_allow,
            )
        else:
            active = base

        self.policy = active
        self.minimum_required_net_edge_bps = active.minimum_required_net_edge_bps
        self.minimum_profitable_trade_size = active.minimum_profitable_trade_size
        self.cooldown_minutes = active.cooldown_minutes
        self.max_trades_per_symbol_per_cycle = active.maximum_symbol_frequency

        want_dev = bool(active.allow_dev_override)
        if want_dev and not _dev_force_allow_permitted():
            raise AntiBleedGuardConfigurationError(
                "dev_force_allow=True is restricted to explicit development/test environments"
            )
        self.dev_force_allow = want_dev
        self.state_file = state_file

        self.state = self._load_state()

    def with_policy(self, policy: AntiBleedPolicy) -> "AntiBleedGuard":
        """Return a new guard bound to ``policy`` sharing the same state file."""
        return AntiBleedGuard(policy=policy, state_file=self.state_file)

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
        policy: Optional[AntiBleedPolicy] = None,
    ) -> Dict[str, Any]:

        active = policy if policy is not None else self.policy
        if not isinstance(active, AntiBleedPolicy):
            raise AntiBleedPolicyError("evaluate policy must be an AntiBleedPolicy instance")

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
            "minimum_required_net_edge_bps": active.minimum_required_net_edge_bps,
            "minimum_profitable_trade_size": active.minimum_profitable_trade_size,
            "anti_bleed_policy": active.name,
            "policy_id": active.policy_id,
            "policy_version": active.policy_version,
            "cooldown_active": cooldown_active,
            "cooldown_until": cooldown_until,
            "timestamp": now.isoformat(),
        }

        # -----------------------------
        # REJECTION RULES (order unchanged)
        # -----------------------------

        if expected_move_bps <= total_cost_bps:
            return self._reject(decision, "expected_move_below_cost", active)

        if net_edge_bps < active.minimum_required_net_edge_bps:
            return self._reject(decision, "insufficient_net_edge", active)

        if trade_size < active.minimum_profitable_trade_size:
            return self._reject(decision, "trade_size_too_small", active)

        if cooldown_active:
            return self._reject(decision, "cooldown_active", active)

        # -----------------------------
        # APPROVED → UPDATE STATE
        # -----------------------------
        self._update_trade_state(symbol, now, cooldown_minutes=active.cooldown_minutes)

        return decision

    # -----------------------------
    # INTERNAL HELPERS
    # -----------------------------

    def _reject(
        self,
        decision: Dict[str, Any],
        reason: str,
        policy: Optional[AntiBleedPolicy] = None,
    ) -> Dict[str, Any]:
        decision["approved"] = False
        decision["reason"] = reason

        self._log_rejection(decision)

        active = policy if policy is not None else self.policy
        allow_override = bool(active.allow_dev_override) and self.dev_force_allow
        if allow_override:
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

    def _update_trade_state(self, symbol: str, now: datetime, cooldown_minutes: Optional[int] = None):

        minutes = int(self.cooldown_minutes if cooldown_minutes is None else cooldown_minutes)
        cooldown_until = now + timedelta(minutes=minutes)

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
            f"policy_id={decision.get('policy_id', '')} | "
            f"policy_version={decision.get('policy_version', '')} | "
            f"reason={decision['reason']} | "
            f"time={decision['timestamp']}"
        )

        print(log_line)
