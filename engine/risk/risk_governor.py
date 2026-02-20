"""
RiskGovernor v4.5 – Institutional CORE Policy (EquityAuthority + PnLTracker)
Capital Strata Systems

Keeps:
- Regime-aware scaling
- Anti-martingale loss compression
- Progressive drawdown throttle
- Hard 20% drawdown rejection
- Volatility compression
- Spread penalty
- High-risk news clamp
- validate_trade adapter for ExecutionGate compatibility

Changes:
- Equity is sourced from EquityAuthority when bound (single source of truth)
- Multi-timeframe PnL tracking now uses PnLTracker (append-only journal)
- InstrumentPerformanceLedger dependency removed
- Transitional fallback supported ONLY if authority not yet bound
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from engine.equity_authority import EquityAuthority
from engine.performance.pnl_tracker import PnLTracker


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

    def __init__(
        self,
        equity_authority: Optional[EquityAuthority] = None,
        pnl_tracker: Optional[PnLTracker] = None,
    ) -> None:
        self.equity_authority = equity_authority
        self.tracker = pnl_tracker
        self.reset_session_state()

    # --------------------------------------------------------
    # Binding (safe for late initialization)
    # --------------------------------------------------------

    def bind_equity_authority(self, equity_authority: EquityAuthority) -> None:
        self.equity_authority = equity_authority

    def bind_pnl_tracker(self, pnl_tracker: PnLTracker) -> None:
        self.tracker = pnl_tracker

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
    # Session state control (NO SHADOW EQUITY)
    # ========================================================

    def reset_session_state(self) -> None:
        self.daily_pnl: float = 0.0
        self.consecutive_losses: int = 0
        self.trades_today: int = 0

        # Transitional fallback only (used ONLY when authority not bound yet)
        self._fallback_equity: Optional[float] = None
        self._fallback_equity_peak: Optional[float] = None

    # ========================================================
    # PnL recording (completed trades)
    # ========================================================

    def record_trade_outcome(
        self,
        pnl: float,
        *,
        instrument: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        pnl = float(pnl)
        self.daily_pnl += pnl
        self.trades_today += 1

        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        # Append-only journal + multi-timeframe buckets
        if self.tracker is not None and instrument:
            ts = timestamp or datetime.now(timezone.utc)
            self.tracker.record_trade(
                instrument=str(instrument),
                realized_pnl=pnl,
                unrealized_pnl=0.0,
                timestamp=ts,
            )

        # Transitional fallback equity tracking (ONLY if authority not bound)
        if self.equity_authority is None:
            if self._fallback_equity is None:
                return
            self._fallback_equity += pnl
            if self._fallback_equity_peak is None:
                self._fallback_equity_peak = self._fallback_equity
            else:
                self._fallback_equity_peak = max(self._fallback_equity_peak, self._fallback_equity)

    # ========================================================
    # Equity + Drawdown (single source when bound)
    # ========================================================

    def _equity_and_peak(self, equity_input: Optional[float] = None) -> (Optional[float], Optional[float], str):
        """
        Returns (equity, equity_peak, source)
        source: 'authority' | 'input_fallback' | 'missing'
        """
        if self.equity_authority is not None:
            try:
                eq = float(self.equity_authority.current_equity())
                pk = float(self.equity_authority.peak_equity())
                return eq, pk, "authority"
            except Exception:
                # If authority exists but not bound, fall back to input below
                pass

        if equity_input is not None:
            eq = float(equity_input)
            if self._fallback_equity is None:
                self._fallback_equity = eq
            if self._fallback_equity_peak is None:
                self._fallback_equity_peak = eq
            else:
                self._fallback_equity_peak = max(self._fallback_equity_peak, eq)
            return float(self._fallback_equity), float(self._fallback_equity_peak), "input_fallback"

        return None, None, "missing"

    def _drawdown_multiplier(self, equity: Optional[float], equity_peak: Optional[float]) -> float:
        if equity is None or equity_peak is None:
            return 1.0
        if equity_peak == 0:
            return 1.0

        dd = (equity_peak - equity) / equity_peak

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

        eq, pk, source = self._equity_and_peak(equity_input=equity)
        if eq is None:
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="equity_missing",
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

        dd_mult = self._drawdown_multiplier(eq, pk)
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

        equity_risk = eq * effective_risk_pct
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

        reason = "ok"
        if source != "authority":
            # Transitional visibility: tells us we still haven't bound EquityAuthority in runtime init
            reason = f"ok_{source}"

        return RiskDecision(
            ok=True,
            status="APPROVED_WITH_ADJUSTMENT" if adjusted else "APPROVED",
            reason=reason,
            requested_notional=float(requested_notional),
            recommended_notional=float(recommended_notional),
            equity_risk=float(equity_risk),
            risk_pct=float(effective_risk_pct),
            adjusted=adjusted,
        ).as_dict()

    # ========================================================
    # Core Evaluation (legacy interface)
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
        equity: Optional[float] = None,
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

        eq, pk, source = self._equity_and_peak(equity_input=equity)
        if eq is None:
            return RiskDecision(
                ok=False,
                status="REJECTED",
                reason="equity_missing",
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

        dd_mult = self._drawdown_multiplier(eq, pk)
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

        # Anti-martingale loss compression
        if self.consecutive_losses >= 2:
            risk_pct *= self.LOSS_STREAK_COMPRESSION

        # Regime-aware scaling
        if regime_persistence is not None:
            risk_pct *= float(regime_persistence)

        # Volatility compression
        if vol_ratio is not None and vol_ratio > 1.5:
            risk_pct *= 0.5

        # Spread penalty
        if spread_bps is not None and spread_bps > 3:
            risk_pct *= 0.75

        # High-risk news clamp
        if high_risk_news:
            risk_pct *= 0.5

        risk_pct = min(risk_pct, self.MAX_RISK_PCT)

        equity_risk = eq * risk_pct
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

        reason = "ok"
        if source != "authority":
            reason = f"ok_{source}"

        return RiskDecision(
            ok=True,
            status="APPROVED_WITH_ADJUSTMENT" if adjusted else "APPROVED",
            reason=reason,
            requested_notional=notional,
            recommended_notional=recommended_notional,
            equity_risk=equity_risk,
            risk_pct=risk_pct,
            adjusted=adjusted,
        )
