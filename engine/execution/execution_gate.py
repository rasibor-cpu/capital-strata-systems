"""
Execution Gate – Central Trade Approval Layer
Capital Strata Systems / REA

Stack Order:
1) Regime-Aware Controlled Compounding
2) Tiered Drawdown Compression
3) Hard Drawdown Circuit Breaker (20%)
4) RiskGovernor Structural Validation
5) Fail-Closed Enforcement

Institutional-grade capital protection.

Notes:
- This module produces a single authoritative ExecutionDecision envelope.
- Safe default: any error => BLOCK.
- Deterministic "reasons" list for audit logging.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from engine.capital.compounding_engine import CompoundingEngine
from engine.risk.drawdown_scaler import DrawdownScaler
from engine.risk.risk_governor import RiskGovernor

from engine.execution_decision import GateResult, ExecutionDecision, build_execution_decision


# -------------------------
# Config (central policy)
# -------------------------

HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT = 0.20  # 20% peak-to-trough


# -------------------------
# Input snapshot (minimal)
# -------------------------

@dataclass(frozen=True)
class TradeIntent:
    instrument: str
    side: str                      # "buy" | "sell"
    notional: float                # position notional (or value proxy)
    stop_distance_pct: float       # stop distance as pct of price (0.01 = 1%)
    policy: str = "core"           # "core" | "paper" | "test" | etc


@dataclass(frozen=True)
class MarketContext:
    regime_persistence: Optional[float] = None  # 0..1 (optional)
    vol_ratio: Optional[float] = None           # >1 high vol (optional)
    spread_bps: Optional[float] = None          # (optional)
    high_risk_news: Optional[bool] = None       # (optional)


@dataclass(frozen=True)
class EquityContext:
    equity: float
    equity_peak: float


# -------------------------
# Helpers
# -------------------------

def _clamp(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


# -------------------------
# Execution Gate (single authority)
# -------------------------

class ExecutionGate:
    """
    Produces one ExecutionDecision by running the required checks in stack order.
    """

    def __init__(self) -> None:
        self.risk_governor = RiskGovernor()
        self.compounding = CompoundingEngine()
        self.drawdown_scaler = DrawdownScaler()

    # ==========================================================
    # 1) Hard Circuit Breaker
    # ==========================================================
    def _hard_drawdown_check(self, *, equity: float, equity_peak: float) -> Optional[GateResult]:
        if equity_peak <= 0:
            # if peak is unknown/invalid, do NOT auto-block here (other layers may block)
            return None

        dd_pct = (equity_peak - equity) / equity_peak
        if dd_pct >= HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT:
            return GateResult(
                ok=False,
                gate="hard_drawdown_circuit_breaker",
                reason=f"drawdown_pct>={HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT:.2f}",
                data={"drawdown_pct": round(dd_pct, 6)},
            )
        return None

    # ==========================================================
    # Input sanity (fail closed)
    # ==========================================================
    def _validate_inputs(
        self,
        *,
        intent: TradeIntent,
        eq: EquityContext,
    ) -> Optional[GateResult]:

        if intent.notional <= 0:
            return GateResult(
                ok=False,
                gate="input_validation",
                reason="notional<=0",
                data={"notional": intent.notional},
            )

        if intent.stop_distance_pct <= 0:
            return GateResult(
                ok=False,
                gate="input_validation",
                reason="stop_distance_pct<=0",
                data={"stop_distance_pct": intent.stop_distance_pct},
            )

        if eq.equity <= 0:
            return GateResult(
                ok=False,
                gate="input_validation",
                reason="equity<=0",
                data={"equity": eq.equity},
            )

        if eq.equity_peak < 0:
            return GateResult(
                ok=False,
                gate="input_validation",
                reason="equity_peak<0",
                data={"equity_peak": eq.equity_peak},
            )

        side = intent.side.lower().strip()
        if side not in ("buy", "sell"):
            return GateResult(
                ok=False,
                gate="input_validation",
                reason="side_invalid",
                data={"side": intent.side},
            )

        return None

    # ==========================================================
    # Main evaluation (single authoritative decision)
    # ==========================================================
    def evaluate_trade(
        self,
        *,
        intent: TradeIntent,
        eq: EquityContext,
        mkt: Optional[MarketContext] = None,
    ) -> ExecutionDecision:
        """
        Returns ExecutionDecision with:
        - decision: "ALLOW" or "BLOCK"
        - reasons: ordered list of reasons
        - meta: useful computed values for logging/telemetry
        """
        mkt = mkt or MarketContext()

        # Fail-closed envelope
        try:
            # 0) Input validation
            bad = self._validate_inputs(intent=intent, eq=eq)
            if bad:
                return build_execution_decision(
                    decision="BLOCK",
                    reasons=[f"{bad.gate}:{bad.reason}"],
                    gate_results=[bad],
                    meta={"policy": intent.policy, "instrument": intent.instrument},
                )

            # ------------------------------------------------------
            # 1) Controlled Compounding (Regime-aware)
            # ------------------------------------------------------
            # compute_dynamic_risk is expected to return a risk pct (0..1),
            # e.g. 0.005 = 0.5% risk per trade.
            dyn_risk_pct = self.compounding.compute_dynamic_risk(
                equity=eq.equity,
                equity_peak=eq.equity_peak,
                regime_persistence=mkt.regime_persistence,
                vol_ratio=mkt.vol_ratio,
                spread_bps=mkt.spread_bps,
                high_risk_news=mkt.high_risk_news,
                policy=intent.policy,
            )
            dyn_risk_pct = _safe_float(dyn_risk_pct, default=0.0)
            dyn_risk_pct = _clamp(dyn_risk_pct, 0.0, 1.0)

            if dyn_risk_pct <= 0:
                gr = GateResult(
                    ok=False,
                    gate="controlled_compounding",
                    reason="dynamic_risk_pct<=0",
                    data={"dynamic_risk_pct": dyn_risk_pct},
                )
                return build_execution_decision(
                    decision="BLOCK",
                    reasons=[f"{gr.gate}:{gr.reason}"],
                    gate_results=[gr],
                    meta={"policy": intent.policy, "instrument": intent.instrument},
                )

            # ------------------------------------------------------
            # 2) Tiered Drawdown Compression (scales risk down with DD)
            # ------------------------------------------------------
            scaled_risk_pct = self.drawdown_scaler.scale_risk_pct(
                base_risk_pct=dyn_risk_pct,
                equity=eq.equity,
                equity_peak=eq.equity_peak,
                policy=intent.policy,
            )
            scaled_risk_pct = _safe_float(scaled_risk_pct, default=0.0)
            scaled_risk_pct = _clamp(scaled_risk_pct, 0.0, 1.0)

            if scaled_risk_pct <= 0:
                gr = GateResult(
                    ok=False,
                    gate="drawdown_compression",
                    reason="scaled_risk_pct<=0",
                    data={"base_risk_pct": dyn_risk_pct, "scaled_risk_pct": scaled_risk_pct},
                )
                return build_execution_decision(
                    decision="BLOCK",
                    reasons=[f"{gr.gate}:{gr.reason}"],
                    gate_results=[gr],
                    meta={"policy": intent.policy, "instrument": intent.instrument},
                )

            # ------------------------------------------------------
            # 3) Hard Drawdown Circuit Breaker (20% DD)
            # ------------------------------------------------------
            breaker = self._hard_drawdown_check(equity=eq.equity, equity_peak=eq.equity_peak)
            if breaker:
                return build_execution_decision(
                    decision="BLOCK",
                    reasons=[f"{breaker.gate}:{breaker.reason}"],
                    gate_results=[breaker],
                    meta={"policy": intent.policy, "instrument": intent.instrument},
                )

            # ------------------------------------------------------
            # 4) RiskGovernor structural validation + sizing bounds
            # ------------------------------------------------------
            # The risk governor should validate the trade against structural caps.
            # It may also compute max_notional or recommended_notional.
            rg = self.risk_governor.validate_trade(
                instrument=intent.instrument,
                side=intent.side,
                requested_notional=intent.notional,
                stop_distance_pct=intent.stop_distance_pct,
                equity=eq.equity,
                risk_pct=scaled_risk_pct,
                policy=intent.policy,
            )

            # Expectation: rg is dict-like with:
            # - ok: bool
            # - reason: str
            # - data: dict (optional)
            rg_ok = bool(getattr(rg, "get", lambda k, d=None: d)("ok", False)) if rg is not None else False
            rg_reason = getattr(rg, "get", lambda k, d=None: d)("reason", "risk_governor_reject") if rg is not None else "risk_governor_reject"
            rg_data = getattr(rg, "get", lambda k, d=None: d)("data", {}) if rg is not None else {}

            if not rg_ok:
                gr = GateResult(
                    ok=False,
                    gate="risk_governor",
                    reason=str(rg_reason),
                    data=dict(rg_data) if isinstance(rg_data, dict) else {"detail": rg_data},
                )
                return build_execution_decision(
                    decision="BLOCK",
                    reasons=[f"{gr.gate}:{gr.reason}"],
                    gate_results=[gr],
                    meta={
                        "policy": intent.policy,
                        "instrument": intent.instrument,
                        "dynamic_risk_pct": dyn_risk_pct,
                        "scaled_risk_pct": scaled_risk_pct,
                    },
                )

            # ------------------------------------------------------
            # ALLOW
            # ------------------------------------------------------
            allow_gr = GateResult(
                ok=True,
                gate="execution_gate",
                reason="all_checks_passed",
                data={
                    "dynamic_risk_pct": dyn_risk_pct,
                    "scaled_risk_pct": scaled_risk_pct,
                    "risk_governor": dict(rg_data) if isinstance(rg_data, dict) else rg_data,
                },
            )

            return build_execution_decision(
                decision="ALLOW",
                reasons=["execution_gate:all_checks_passed"],
                gate_results=[allow_gr],
                meta={
                    "policy": intent.policy,
                    "instrument": intent.instrument,
                    "dynamic_risk_pct": dyn_risk_pct,
                    "scaled_risk_pct": scaled_risk_pct,
                },
            )

        except Exception as e:
            # Fail-closed
            gr = GateResult(
                ok=False,
                gate="fail_closed",
                reason="exception",
                data={"error": str(e)},
            )
            return build_execution_decision(
                decision="BLOCK",
                reasons=[f"{gr.gate}:{gr.reason}"],
                gate_results=[gr],
                meta={"policy": intent.policy, "instrument": intent.instrument},
            )
