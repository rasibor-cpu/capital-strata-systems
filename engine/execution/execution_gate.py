"""
Execution Gate (Hard-Lock, Pre-Trade)
------------------------------------
Final governance barrier BEFORE any order can be placed.

This module enforces:
- Global execution enable switch
- Max trades/day
- Max concurrent positions
- Per-trade equity risk caps
- Drawdown cap
- Loss streak cooldown rules
- Human override requirements for high-risk trades

It does NOT place orders. It only returns ALLOW/BLOCK decisions + reasons.

IMPORTANT:
- Keep deterministic and auditable.
- BLOCK by default on missing/invalid inputs.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import time


@dataclass(frozen=True)
class ExecutionDecision:
    decision: str           # "ALLOW" | "BLOCK"
    reason: str             # reason code
    meta: Dict[str, Any]


class ExecutionGate:
    """
    Governance thresholds (approved).
    """

    # --- Global hard lock ---
    EXECUTION_ENABLED_DEFAULT: bool = False

    # --- Operational limits (approved) ---
    MAX_TRADES_PER_DAY: int = 10
    MAX_CONCURRENT_POSITIONS: int = 20

    # --- Risk caps (approved) ---
    # Up to 20% of total equity per single trade (bank single-obligor style limit)
    MAX_SINGLE_TRADE_EQUITY_PCT: float = 0.20

    # Drawdown cap (absolute portfolio equity drawdown)
    MAX_DRAWDOWN_PCT: float = 0.25

    # Human override required if a proposed trade risks > 25% of equity
    OVERRIDE_REQUIRED_ABOVE_EQUITY_PCT: float = 0.25

    # --- Cooldown rules (approved) ---
    # 5 losses triggers 12h cooldown (global)
    GLOBAL_LOSS_STREAK_LIMIT: int = 5
    GLOBAL_COOLDOWN_SECONDS: int = 12 * 60 * 60

    # 3 losses per pair triggers pair block
    PAIR_LOSS_STREAK_LIMIT: int = 3

    @classmethod
    def evaluate(
        cls,
        *,
        now_ts: Optional[float],
        execution_enabled: Optional[bool],
        equity: Optional[float],
        peak_equity: Optional[float],
        current_equity: Optional[float],
        proposed_risk_amount: Optional[float],
        trades_today: Optional[int],
        open_positions: Optional[int],
        global_loss_streak: Optional[int],
        global_cooldown_until_ts: Optional[float],
        pair_loss_streak: Optional[int],
        has_human_override: Optional[bool],
        override_confirmations: Optional[int],
        extra: Optional[Dict[str, Any]] = None,
    ) -> ExecutionDecision:
        """
        Inputs must be supplied by the engine state manager / risk engine.

        proposed_risk_amount: worst-case loss amount (in account currency) for this trade
                              after stop placement and slippage assumptions (conservative).

        override_confirmations: count of password confirmations collected (must be >=2)
        """
        meta = extra.copy() if extra else {}
        ts = now_ts if now_ts is not None else time.time()

        # Helper for consistent blocking
        def block(reason: str) -> ExecutionDecision:
            meta.update({"ts": ts})
            return ExecutionDecision("BLOCK", reason, meta)

        def allow(reason: str) -> ExecutionDecision:
            meta.update({"ts": ts})
            return ExecutionDecision("ALLOW", reason, meta)

        # 0) Hard lock: execution enabled
        if execution_enabled is None:
            return block("execution_enabled_missing")
        if execution_enabled is False:
            return block("execution_disabled")

        # 1) Basic required fields
        if any(v is None for v in [equity, peak_equity, current_equity, proposed_risk_amount,
                                   trades_today, open_positions, global_loss_streak,
                                   global_cooldown_until_ts, pair_loss_streak,
                                   has_human_override, override_confirmations]):
            return block("missing_required_inputs")

        if equity <= 0 or peak_equity <= 0 or current_equity <= 0:
            return block("invalid_equity_values")

        if proposed_risk_amount < 0:
            return block("invalid_risk_amount")

        # 2) Daily / concurrent limits
        if trades_today >= cls.MAX_TRADES_PER_DAY:
            return block("max_trades_per_day_reached")

        if open_positions >= cls.MAX_CONCURRENT_POSITIONS:
            return block("max_concurrent_positions_reached")

        # 3) Drawdown cap
        dd = (peak_equity - current_equity) / peak_equity
        meta.update({"drawdown_pct": dd})
        if dd >= cls.MAX_DRAWDOWN_PCT:
            return block("drawdown_cap_reached")

        # 4) Global cooldown
        if global_loss_streak >= cls.GLOBAL_LOSS_STREAK_LIMIT:
            if ts < global_cooldown_until_ts:
                meta.update({"cooldown_until_ts": global_cooldown_until_ts})
                return block("global_cooldown_active")
            # cooldown elapsed → allow continuing, but still cautious
            meta.update({"global_cooldown_elapsed": True})

        # 5) Pair loss streak
        if pair_loss_streak >= cls.PAIR_LOSS_STREAK_LIMIT:
            return block("pair_loss_streak_block")

        # 6) Per-trade equity cap (approved: 20%)
        risk_pct = proposed_risk_amount / equity if equity > 0 else 1.0
        meta.update({"proposed_risk_pct_equity": risk_pct})

        if risk_pct > cls.MAX_SINGLE_TRADE_EQUITY_PCT:
            return block("single_trade_risk_cap_exceeded")

        # 7) Override requirement above 25% equity risk
        # Note: this is stricter than the 20% cap, but we keep it here for completeness and future tuning.
        if risk_pct > cls.OVERRIDE_REQUIRED_ABOVE_EQUITY_PCT:
            # Must have override + double confirmation
            if not has_human_override:
                return block("override_required_missing")
            if override_confirmations < 2:
                return block("override_double_confirm_required")

        return allow("ok")


# Safety invariant
if __name__ == "__main__":
    raise RuntimeError("execution_gate.py is a library module only and must not be executed directly.")
