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

Compatibility:
- This file is signature-agnostic for CompoundingEngine / DrawdownScaler / RiskGovernor.
- It attempts rich calls first, then progressively reduces args if needed.
- Safe default: any exception => BLOCK.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable

from engine.capital.compounding_engine import CompoundingEngine
from engine.risk.drawdown_scaler import DrawdownScaler
from engine.risk.risk_governor import RiskGovernor

from engine.execution_decision import GateResult, ExecutionDecision, build_execution_decision


HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT = 0.20  # 20% peak-to-trough


@dataclass(frozen=True)
class TradeIntent:
    instrument: str
    side: str                      # "buy" | "sell"
    notional: float
    stop_distance_pct: float       # 0.01 = 1%
    policy: str = "core"


@dataclass(frozen=True)
class MarketContext:
    regime_persistence: Optional[float] = None
    vol_ratio: Optional[float] = None
    spread_bps: Optional[float] = None
    high_risk_news: Optional[bool] = None


@dataclass(frozen=True)
class EquityContext:
    equity: float
    equity_peak: float


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


def _call_flexible(func: Callable[..., Any], attempts: List[Dict[str, Any]]) -> Any:
    """
    Try calling func with progressively simpler kwarg sets.
    - If a call fails due to unexpected kwargs / signature mismatch, we retry with a reduced set.
    - Any other exception is still raised (handled by fail-closed upstream).
    """
    last_err: Optional[Exception] = None
    for kwargs in attempts:
        try:
            return func(**kwargs)
        except TypeError as e:
            # Likely signature mismatch (unexpected kwarg / missing positional-only, etc.)
            last_err = e
            continue
    # If we exhausted attempts, raise the last error
    if last_err:
        raise last_err
    raise TypeError("No call attempts provided")


class ExecutionGate:
    def __init__(self) -> None:
        self.risk_governor = RiskGovernor()
        self.compounding = CompoundingEngine()
        self.drawdown_scaler = DrawdownScaler()

    # -------------------------
    # Hard Circuit Breaker
    # -------------------------
    def _hard_drawdown_check(self, *, equity: float, equity_peak: float) -> Optional[GateResult]:
        if equity_peak <= 0:
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

    # -------------------------
    # Input sanity
    # -------------------------
    def _validate_inputs(self, *, intent: TradeIntent, eq: EquityContext) -> Optional[GateResult]:
        if intent.notional <= 0:
            return GateResult(ok=False, gate="input_validation", reason="notional<=0", data={"notional": intent.notional})
        if intent.stop_distance_pct <= 0:
            return GateResult(
                ok=False,
                gate="input_validation",
                reason="stop_distance_pct<=0",
                data={"stop_distance_pct": intent.stop_distance_pct},
            )
        if eq.equity <= 0:
            return GateResult(ok=False, gate="input_validation", reason="equity<=0", data={"equity": eq.equity})
        if eq.equity_peak < 0:
            return GateResult(ok=False, gate="input_validation", reason="equity_peak<0", data={"equity_peak": eq.equity_peak})

        side = intent.side.lower().strip()
        if side not in ("buy", "sell"):
            return GateResult(ok=False, gate="input_validation", reason="side_invalid", data={"side": intent.side})

        return None

    # -------------------------
    # Main evaluation
    # -------------------------
    def evaluate_trade(
        self,
        *,
        intent: TradeIntent,
        eq: EquityContext,
        mkt: Optional[MarketContext] = None,
    ) -> ExecutionDecision:

        mkt = mkt or MarketContext()

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

            # 1) Controlled Compounding (try rich call, then simpler)
            dyn_attempts = [
                {
                    "equity": eq.equity,
                    "equity_peak": eq.equity_peak,
                    "regime_persistence": mkt.regime_persistence,
                    "vol_ratio": mkt.vol_ratio,
                    "spread_bps": mkt.spread_bps,
                    "high_risk_news": mkt.high_risk_news,
                    "policy": intent.policy,
                },
                {
                    "equity": eq.equity,
                    "equity_peak": eq.equity_peak,
                    "regime_persistence": mkt.regime_persistence,
                    "vol_ratio": mkt.vol_ratio,
                },
                {
                    "equity": eq.equity,
                    "equity_peak": eq.equity_peak,
                },
            ]

            dyn_risk_pct = _call_flexible(self.compounding.compute_dynamic_risk, dyn_attempts)
            dyn_risk_pct = _clamp(_safe_float(dyn_risk_pct, default=0.0), 0.0, 1.0)

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

            # 2) Tiered Drawdown Compression (try rich call, then simpler)
            scale_attempts = [
                {
                    "base_risk_pct": dyn_risk_pct,
                    "equity": eq.equity,
                    "equity_peak": eq.equity_peak,
                    "policy": intent.policy,
                },
                {
                    "base_risk_pct": dyn_risk_pct,
                    "equity": eq.equity,
                    "equity_peak": eq.equity_peak,
                },
                {
                    "risk_pct": dyn_risk_pct,  # alternate common naming
                    "equity": eq.equity,
                    "equity_peak": eq.equity_peak,
                },
            ]

            # Support two possible method names in DrawdownScaler
            if hasattr(self.drawdown_scaler, "scale_risk_pct"):
                scaled = _call_flexible(self.drawdown_scaler.scale_risk_pct, scale_attempts)  # type: ignore[attr-defined]
            else:
                # fallback common name
                scaled = _call_flexible(self.drawdown_scaler.scale, scale_attempts)  # type: ignore[attr-defined]

            scaled_risk_pct = _clamp(_safe_float(scaled, default=0.0), 0.0, 1.0)

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

            # 3) Hard Drawdown Circuit Breaker
            breaker = self._hard_drawdown_check(equity=eq.equity, equity_peak=eq.equity_peak)
            if breaker:
                return build_execution_decision(
                    decision="BLOCK",
                    reasons=[f"{breaker.gate}:{breaker.reason}"],
                    gate_results=[breaker],
                    meta={"policy": intent.policy, "instrument": intent.instrument},
                )

            # 4) RiskGovernor structural validation (try rich call, then simpler)
            rg_attempts = [
                {
                    "instrument": intent.instrument,
                    "side": intent.side,
                    "requested_notional": intent.notional,
                    "stop_distance_pct": intent.stop_distance_pct,
                    "equity": eq.equity,
                    "risk_pct": scaled_risk_pct,
                    "policy": intent.policy,
                },
                {
                    "instrument": intent.instrument,
                    "side": intent.side,
                    "notional": intent.notional,
                    "stop_distance_pct": intent.stop_distance_pct,
                    "equity": eq.equity,
                    "risk_pct": scaled_risk_pct,
                },
                {
                    "instrument": intent.instrument,
                    "side": intent.side,
                    "notional": intent.notional,
                    "equity": eq.equity,
                },
            ]

            if hasattr(self.risk_governor, "validate_trade"):
                rg = _call_flexible(self.risk_governor.validate_trade, rg_attempts)  # type: ignore[attr-defined]
            else:
                rg = _call_flexible(self.risk_governor.validate, rg_attempts)  # type: ignore[attr-defined]

            # Normalize RG response
            rg_ok = False
            rg_reason = "risk_governor_reject"
            rg_data: Any = {}

            if isinstance(rg, dict):
                rg_ok = bool(rg.get("ok", False))
                rg_reason = str(rg.get("reason", rg_reason))
                rg_data = rg.get("data", {})
            else:
                # if RG returns boolean or custom object
                if isinstance(rg, bool):
                    rg_ok = rg
                else:
                    rg_ok = bool(getattr(rg, "ok", False))
                    rg_reason = str(getattr(rg, "reason", rg_reason))
                    rg_data = getattr(rg, "data", {})

            if not rg_ok:
                gr = GateResult(
                    ok=False,
                    gate="risk_governor",
                    reason=rg_reason,
                    data=rg_data if isinstance(rg_data, dict) else {"detail": rg_data},
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

            # ALLOW
            allow_gr = GateResult(
                ok=True,
                gate="execution_gate",
                reason="all_checks_passed",
                data={
                    "dynamic_risk_pct": dyn_risk_pct,
                    "scaled_risk_pct": scaled_risk_pct,
                    "risk_governor": rg_data,
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
            gr = GateResult(ok=False, gate="fail_closed", reason="exception", data={"error": str(e)})
            return build_execution_decision(
                decision="BLOCK",
                reasons=[f"{gr.gate}:{gr.reason}"],
                gate_results=[gr],
                meta={"policy": intent.policy, "instrument": intent.instrument},
            )
