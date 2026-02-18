"""
RiskGovernor v3 – Institutional CORE Policy
Capital Strata Systems

Features:
- Regime-aware scaling
- Anti-martingale loss compression
- Progressive drawdown throttle
- Hard 20% drawdown rejection
- Volatility compression
- Spread penalty
- High-risk news clamp
- Primitive allow_trade interface

Institutional hardening added:
- policy_fingerprint() + policy_hash() for session-init logging
- reset_session_state() for deterministic session resets
- validate_trade() adapter for ExecutionGate compatibility (uses provided risk_pct)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any


# ============================================================
# Decision Object
# ============================================================

@dataclass
class RiskDecision:
    ok: bool
    status: str
    reason: str
    requested_notional: float
    recommended_notional: float
    equity_risk: float
    risk_pct: float
    adjusted: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "reason": self.reason,
            "requested_notional": self.requested_notional,
            "recommended_notional": self.recommended_notional,
            "equity_risk": self.equity_risk,
            "risk_pct": self.risk_pct,
            "adjusted": self.adjusted,
        }


# ============================================================
# Governor
# ============================================================

class RiskGovernor:
    # ---- Core policy constants (immutable per session) ----
    BASE_RISK_PCT = 0.01
    MAX_RISK_PCT = 0.02
    MAX_DRAWDOWN_LIMIT = 0.20
    LOSS_STREAK_COMPRESSION = 0.5
    MIN_NOTIONAL = 1.0

    def __init__(self) -> None:
        # session state (mutable, but should be reset per session)
        self.reset_session_state()

    # ========================================================
    # Policy fingerprint (for logging at session init)
    # ========================================================

    @classmethod
    def policy_fingerprint(cls) -> Dict[str, Any]:
        return {
            "BASE_RISK_PCT": cls.BASE_RISK_PCT,
            "MAX_RISK_PCT": cls.MAX_RISK_PCT,
            "MAX_DRAWDOWN_LIMIT": cls.MAX_DRAWDOWN_LIMIT,
            "LOSS_STREAK_COMPRESSION": cls.LOSS_STREAK_COMPRESSION,
            "MIN_NOTIONAL": cls.MIN_NOTIONAL,
        }

    @classmethod
    def policy_hash(cls) -> str:
        payload = json.dumps(cls.policy_fingerprint(), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    # ========================================================
    # Session state control
    # ========================================================

    def reset_session_state(self) -> None:
        self.equity: Optional[float] = None
        self.equity_peak: Optional[float] = None
        self.daily_pnl: float = 0.0
        self.consecutive_losses: int = 0
        self.trades_today: int = 0

    # ========================================================
    # Context
    # ========================================================

    def set_equity(self, equity: float) -> None:
        self.equity = float(equity)
        if self.equity_peak is None:
            self.equity_peak = float(equity)
        else:
            self.equity_peak = max(self.equity_peak, float(equity))

    def record_trade_outcome(self, pnl: float) -> None:
        pnl = float(pnl)
        self.daily_pnl += pnl
        self.trades_today += 1

        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        if self.equity is not None:
            self.equity += pnl
            self.equity_peak = max(self.equity_peak or self.equity, self.equity)

    # ========================================================
    # Drawdown Throttle (CORE Policy)
    # ========================================================

    def _drawdown_multiplier(self) -> float:
        if self.equity is None or self.equity_peak is None:
            return 1.0
        if self.equity_peak == 0:
            return 1.0

        dd = (self.equity_peak - self.equity) / self.equity_peak

        if dd >= self.MAX_DRAWDOWN_LIMIT:
            return 0.0
        elif dd >= 0.15:
            return 0.25
        elif dd >= 0.10:
            return 0.50
        elif dd >= 0.05:
            return 0.75
        else:
            return 1.0

    # ========================================================
    # Adapter method for ExecutionGate compatibility
    # Uses provided risk_pct (already computed upstream).
    # ========================================================

    def validate_trade(
        self,
        *,
        instrument: str,
        side: str,
        requested_notional: float,
        stop_distance_pct: float,
        equity: float,
        risk_pct: float,
        policy: str = "core",
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        # policy must not be silently accepted if unknown
        if policy != "core":
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="unsupported_policy",
                requested_notional=requested_notional,
                recommended_notional=0.0,
                equity_risk=0.0,
                risk_pct=0.0,
                adjusted=False,
            ).as_dict()

        # initialize / update equity context
        self.set_equity(equity)

        if self.equity is None:
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="equity_not_initialized",
                requested_notional=requested_notional,
                recommended_notional=0.0,
                equity_risk=0.0,
                risk_pct=0.0,
                adjusted=False,
            ).as_dict()

        if stop_distance_pct <= 0:
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="invalid_stop_distance",
                requested_notional=requested_notional,
                recommended_notional=0.0,
                equity_risk=0.0,
                risk_pct=0.0,
                adjusted=False,
            ).as_dict()

        # Hard drawdown rejection (defensive)
        dd_mult = self._drawdown_multiplier()
        if dd_mult == 0.0:
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="hard_drawdown_limit_reached",
                requested_notional=requested_notional,
                recommended_notional=0.0,
                equity_risk=0.0,
                risk_pct=0.0,
                adjusted=False,
            ).as_dict()

        # Use upstream risk_pct, but cap it to MAX_RISK_PCT
        effective_risk_pct = float(risk_pct or 0.0)
        if effective_risk_pct <= 0:
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="risk_pct<=0",
                requested_notional=requested_notional,
                recommended_notional=0.0,
                equity_risk=0.0,
                risk_pct=0.0,
                adjusted=False,
            ).as_dict()

        effective_risk_pct = min(effective_risk_pct, self.MAX_RISK_PCT)

        equity_risk = self.equity * effective_risk_pct
        max_allowed_notional = equity_risk / stop_distance_pct
        recommended_notional = min(float(requested_notional), float(max_allowed_notional))

        if recommended_notional < self.MIN_NOTIONAL:
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="notional_too_small_after_risk_adjustment",
                requested_notional=requested_notional,
                recommended_notional=0.0,
                equity_risk=equity_risk,
                risk_pct=effective_risk_pct,
                adjusted=True,
            ).as_dict()

        adjusted = recommended_notional < float(requested_notional)

        return RiskDecision(
            ok=True,
            status="APPROVED_WITH_ADJUSTMENT" if adjusted else "APPROVED",
            reason="ok",
            requested_notional=float(requested_notional),
            recommended_notional=float(recommended_notional),
            equity_risk=float(equity_risk),
            risk_pct=float(effective_risk_pct),
            adjusted=adjusted,
        ).as_dict()

    # ========================================================
    # Core Evaluation (legacy interface)
    # Computes risk_pct internally.
    # ========================================================

    def allow_trade(
        self,
        *,
        instrument: str,
        side: str,
        notional: float,
        stop_distance_pct: float,
        policy: str = "core",
        regime_persistence: Optional[float] = None,
        vol_ratio: Optional[float] = None,
        spread_bps: Optional[float] = None,
        high_risk_news: Optional[bool] = None,
    ) -> RiskDecision:

        if policy != "core":
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="unsupported_policy",
                requested_notional=notional,
                recommended_notional=0.0,
                equity_risk=0.0,
                risk_pct=0.0,
                adjusted=False,
            )

        if self.equity is None:
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="equity_not_initialized",
                requested_notional=notional,
                recommended_notional=0.0,
                equity_risk=0.0,
                risk_pct=0.0,
                adjusted=False,
            )

        if stop_distance_pct <= 0:
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="invalid_stop_distance",
                requested_notional=notional,
                recommended_notional=0.0,
                equity_risk=0.0,
                risk_pct=0.0,
                adjusted=False,
            )

        # -------------------------
        # Base Risk × Drawdown Throttle
        # -------------------------

        dd_mult = self._drawdown_multiplier()

        if dd_mult == 0.0:
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="hard_drawdown_limit_reached",
                requested_notional=notional,
                recommended_notional=0.0,
                equity_risk=0.0,
                risk_pct=0.0,
                adjusted=False,
            )

        risk_pct = self.BASE_RISK_PCT * dd_mult

        # -------------------------
        # Anti-Martingale
        # -------------------------

        if self.consecutive_losses >= 2:
            risk_pct *= self.LOSS_STREAK_COMPRESSION

        # -------------------------
        # Regime Scaling
        # -------------------------

        if regime_persistence is not None:
            risk_pct *= float(regime_persistence)

        # -------------------------
        # Volatility Compression
        # -------------------------

        if vol_ratio is not None and vol_ratio > 1.5:
            risk_pct *= 0.5

        # -------------------------
        # Spread Penalty
        # -------------------------

        if spread_bps is not None and spread_bps > 3:
            risk_pct *= 0.75

        # -------------------------
        # News Clamp
        # -------------------------

        if high_risk_news:
            risk_pct *= 0.5

        risk_pct = min(risk_pct, self.MAX_RISK_PCT)

        equity_risk = self.equity * risk_pct
        max_allowed_notional = equity_risk / stop_distance_pct
        recommended_notional = min(notional, max_allowed_notional)

        if recommended_notional < self.MIN_NOTIONAL:
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="notional_too_small_after_risk_adjustment",
                requested_notional=notional,
                recommended_notional=0.0,
                equity_risk=equity_risk,
                risk_pct=risk_pct,
                adjusted=True,
            )

        adjusted = recommended_notional < notional

        return RiskDecision(
            ok=True,
            status="APPROVED_WITH_ADJUSTMENT" if adjusted else "APPROVED",
            reason="ok",
            requested_notional=notional,
            recommended_notional=recommended_notional,
            equity_risk=equity_risk,
            risk_pct=risk_pct,
            adjusted=adjusted,
        )
