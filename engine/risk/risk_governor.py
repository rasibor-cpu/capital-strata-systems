"""
Risk Governor – Capital Strata Systems / REA Capital Trading Engine

Phase 1 focus:
- Deterministic, testable caps + sizing
- Fail-closed trade decisions
- No backend imports (avoid circular imports)
- Headless-compatible (pure python, stdlib only)

Key outputs (used by headless endpoint):
- caps: risk_budget_pct, max_position_notional_pct, regime, cooldown_active, reasons
- sizing (FX): risk_budget_abs, theoretical_notional, max_notional_abs, final_notional, capital_utilization_pct
- sizing (Futures): contracts, margin_required, risk_per_contract, total_risk, bucket_utilization_pct
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from engine.capital.futures_capital_bucket import FuturesCapitalBucket


# ---------------------------
# Helpers
# ---------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


# ---------------------------
# Configuration
# ---------------------------

@dataclass(frozen=True)
class DrawdownBand:
    name: str
    max_dd: float  # upper bound inclusive for that band (e.g. 0.03 = 3%)
    risk_budget_pct: float  # fraction of equity allowed at risk (e.g. 0.005 = 0.5%)
    max_position_notional_pct: float  # max gross notional as % of equity (e.g. 0.20 = 20%)


DEFAULT_DRAWDOWN_BANDS: List[DrawdownBand] = [
    DrawdownBand(name="drawdown_band_0_3", max_dd=0.03, risk_budget_pct=0.005, max_position_notional_pct=0.20),
    DrawdownBand(name="drawdown_band_3_6", max_dd=0.06, risk_budget_pct=0.0035, max_position_notional_pct=0.12),
    DrawdownBand(name="drawdown_band_6_10", max_dd=0.10, risk_budget_pct=0.0020, max_position_notional_pct=0.08),
    DrawdownBand(name="drawdown_band_10_15", max_dd=0.15, risk_budget_pct=0.0010, max_position_notional_pct=0.05),
    # beyond this: effectively "halt / micro-mode only"
]

# Cooldown policy (Phase 1)
MAX_CONSECUTIVE_LOSSES_BEFORE_COOLDOWN = 3
COOLDOWN_MINUTES = 30

# Micro-mode triggers (Phase 1)
MICRO_MODE_DRAWDOWN_TRIGGER = 0.06     # >=6% drawdown -> micro mode
MICRO_MODE_CONSEC_LOSSES_TRIGGER = 2   # >=2 consecutive losses -> micro mode scaling


# ---------------------------
# Core Governor
# ---------------------------

class RiskGovernor:
    """
    Decision engine.

    Input:
      - instrument: symbol/pair
      - equity_risk: requested risk amount or proxy (Phase 1: accepted but not trusted)
      - state: dict containing session risk state

    Output:
      dict with:
        decision: "ALLOW" | "BLOCK"
        policy: string
        reasons: list[str]
        caps: dict
    """

    def __init__(self, bands: Optional[List[DrawdownBand]] = None):
        self.bands = bands or DEFAULT_DRAWDOWN_BANDS

    # ---------- Public API ----------

    def evaluate(
        self,
        *,
        instrument: str,
        equity_risk: float,
        state: Dict[str, Any],
        current_equity: Optional[float] = None,
        peak_equity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Fail-closed:
          - If required state fields are missing, we default them safely.
          - If cooldown is active, BLOCK.
          - Otherwise ALLOW (Phase 1) but return tight caps.
        """

        eq = _safe_float(current_equity, _safe_float(state.get("equity", 100000.0), 100000.0))
        peak = _safe_float(peak_equity, _safe_float(state.get("equity_peak", eq), eq))
        peak = max(peak, 1.0)  # avoid division by zero

        dd = self._drawdown_pct(eq, peak)

        # Cooldown check
        cooldown_until = state.get("cooldown_until")
        if cooldown_until:
            try:
                until_dt = datetime.fromisoformat(str(cooldown_until))
                if until_dt.tzinfo is None:
                    until_dt = until_dt.replace(tzinfo=timezone.utc)
                if _utc_now() < until_dt:
                    caps = self._caps(eq, peak, dd, state)
                    return {
                        "decision": "BLOCK",
                        "policy": "cooldown_active",
                        "reasons": ["cooldown_active"],
                        "caps": caps,
                    }
            except Exception:
                caps = self._caps(eq, peak, dd, state)
                return {
                    "decision": "BLOCK",
                    "policy": "cooldown_active",
                    "reasons": ["cooldown_active", "cooldown_timestamp_malformed"],
                    "caps": caps,
                }

        # Drawdown hard-stop (beyond bands)
        if dd > self.bands[-1].max_dd:
            caps = self._caps(eq, peak, dd, state, force_micro=True)
            return {
                "decision": "BLOCK",
                "policy": "drawdown_hard_stop",
                "reasons": ["drawdown_hard_stop"],
                "caps": caps,
            }

        # Phase 1: allow trade requests, but caps determine final sizing downstream
        caps = self._caps(eq, peak, dd, state)

        reasons = list(caps.get("reasons", []))
        if _safe_float(equity_risk, 0.0) < 0:
            reasons.append("equity_risk_negative_ignored")

        return {
            "decision": "ALLOW",
            "policy": "phase1_allow_with_caps",
            "reasons": reasons,
            "caps": caps,
        }

    # ---------------------------------------------------
    # Futures Capital Enforcement (Phase 2A)
    # ---------------------------------------------------

    def validate_futures_capital(
        self,
        *,
        total_equity: float,
        proposed_futures_exposure: float,
    ) -> bool:
        """
        Validates that futures exposure stays within the 25% allocation bucket.

        This does NOT enable futures execution.
        It is a structural validation layer only.
        """
        bucket = FuturesCapitalBucket(total_equity=total_equity)
        return bucket.futures_within_limit(proposed_futures_exposure)

    def compute_caps_and_sizing(
        self,
        *,
        current_equity: float,
        peak_equity: float,
        current_open_positions: int,
        trades_today: int,
        consecutive_losses: int,
    ) -> Dict[str, Any]:
        """
        Headless helper: compute caps + deterministic sizing suggestion.
        This is what your /engine/headless/run endpoint should use.

        Returns:
          {
            "caps": {...},
            "sizing": {...}
          }
        """
        eq = max(_safe_float(current_equity, 100000.0), 1.0)
        peak = max(_safe_float(peak_equity, eq), 1.0)
        dd = self._drawdown_pct(eq, peak)

        # NOTE: This stub is intentionally minimal for Phase 1.
        # Futures sizing is enabled by setting state_stub["asset_class"]="futures"
        # and supplying the futures fields documented in _futures_sizing().
        state_stub: Dict[str, Any] = {
            "open_positions": _safe_int(current_open_positions, 0),
            "trades_today": _safe_int(trades_today, 0),
            "consecutive_losses": _safe_int(consecutive_losses, 0),
            "equity": eq,
            "equity_peak": peak,
            # "asset_class": "fx",  # default implied
        }

        caps = self._caps(eq, peak, dd, state_stub)

        asset_class = state_stub.get("asset_class", "fx")

        if asset_class == "futures":
            sizing = self._futures_sizing(eq, caps, state_stub)
        else:
            sizing = self._sizing(eq, caps)

        return {"caps": caps, "sizing": sizing}

    # ---------- Internal ----------

    def _drawdown_pct(self, equity: float, peak: float) -> float:
        if peak <= 0:
            return 0.0
        dd = (peak - equity) / peak
        if dd < 0:
            return 0.0
        if dd > 1:
            return 1.0
        return dd

    def _select_band(self, dd: float) -> DrawdownBand:
        for b in self.bands:
            if dd <= b.max_dd:
                return b
        return self.bands[-1]

    def _caps(
        self,
        equity: float,
        peak: float,
        dd: float,
        state: Dict[str, Any],
        *,
        force_micro: bool = False,
    ) -> Dict[str, Any]:
        band = self._select_band(dd)

        reasons: List[str] = [band.name]

        # Regime (Phase 1)
        regime = "normal"
        if dd >= 0.03:
            regime = "defensive"
            reasons.append("regime_defensive")
        else:
            reasons.append("regime_normal")

        # Micro-mode scaling (defensive throttle)
        consec = _safe_int(state.get("consecutive_losses"), 0)
        micro = force_micro or (dd >= MICRO_MODE_DRAWDOWN_TRIGGER) or (consec >= MICRO_MODE_CONSEC_LOSSES_TRIGGER)

        risk_budget_pct = band.risk_budget_pct
        max_pos_pct = band.max_position_notional_pct

        if micro:
            reasons.append("micro_mode_active")
            risk_budget_pct = max(risk_budget_pct * 0.5, 0.0005)  # floor at 0.05%
            max_pos_pct = max(max_pos_pct * 0.5, 0.02)            # floor at 2%

        # Cooldown flag (informational; actual block is handled in evaluate())
        cooldown_active = False
        cooldown_until = state.get("cooldown_until")
        if cooldown_until:
            try:
                until_dt = datetime.fromisoformat(str(cooldown_until))
                if until_dt.tzinfo is None:
                    until_dt = until_dt.replace(tzinfo=timezone.utc)
                cooldown_active = _utc_now() < until_dt
            except Exception:
                cooldown_active = True
                reasons.append("cooldown_timestamp_malformed")

        return {
            "ok": True,
            "equity": float(equity),
            "equity_peak": float(peak),
            "drawdown_pct": float(dd),
            "risk_budget_pct": float(risk_budget_pct),
            "max_position_notional_pct": float(max_pos_pct),
            "regime": regime,
            "cooldown_active": bool(cooldown_active),
            "reasons": reasons,
            "source": "AdaptiveCapScaler",
        }

    def _sizing(self, equity: float, caps: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministic sizing for Phase 1 (FX-style notional sizing).

        Assumptions:
          - theoretical_notional = equity * 0.50 (placeholder heuristic)
          - max_notional_abs = equity * max_position_notional_pct (hard cap)
          - final_notional = min(theoretical_notional, max_notional_abs)
        """
        risk_budget_pct = _safe_float(caps.get("risk_budget_pct"), 0.0)
        max_pos_pct = _safe_float(caps.get("max_position_notional_pct"), 0.0)

        risk_budget_abs = equity * risk_budget_pct

        theoretical_notional = equity * 0.50
        max_notional_abs = equity * max_pos_pct
        final_notional = min(theoretical_notional, max_notional_abs)

        cap_util = 0.0
        if equity > 0:
            cap_util = final_notional / equity
            if cap_util < 0:
                cap_util = 0.0
            if cap_util > 1:
                cap_util = 1.0

        return {
            "ok": True,
            "risk_budget_abs": float(risk_budget_abs),
            "theoretical_notional": float(theoretical_notional),
            "max_notional_abs": float(max_notional_abs),
            "final_notional": float(final_notional),
            "capital_utilization_pct": float(cap_util),
        }

    def _futures_sizing(
        self,
        equity: float,
        caps: Dict[str, Any],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Futures sizing is contract-aware and margin-aware.
        Fail-closed unless required inputs are provided in `state`.

        Required state keys:
          - futures_contract_spec: dict
          - stop_distance_points: float
          - risk_pct: float (percent, e.g. 1.0 for 1%)
          - futures_capital_bucket: float (bucket amount in currency)
        """
        # Local import to avoid pulling futures modules for FX-only runs.
        from engine.capital.futures_risk_model import FuturesRiskModel, FuturesContractSpec

        contract_spec = state.get("futures_contract_spec")
        stop_distance = state.get("stop_distance_points")
        risk_pct = state.get("risk_pct")
        futures_bucket = state.get("futures_capital_bucket")

        if not isinstance(contract_spec, dict):
            return {"ok": False, "reason": "missing_futures_contract_spec"}

        if not isinstance(stop_distance, (int, float)) or float(stop_distance) <= 0:
            return {"ok": False, "reason": "missing_or_invalid_stop_distance_points"}

        if not isinstance(risk_pct, (int, float)) or float(risk_pct) <= 0:
            return {"ok": False, "reason": "missing_or_invalid_risk_pct"}

        if not isinstance(futures_bucket, (int, float)) or float(futures_bucket) <= 0:
            return {"ok": False, "reason": "missing_or_invalid_futures_capital_bucket"}

        try:
            contract = FuturesContractSpec(**contract_spec)
        except Exception as e:
            return {"ok": False, "reason": f"invalid_futures_contract_spec:{type(e).__name__}"}

        model = FuturesRiskModel()

        result = model.size_position(
            equity=float(equity),
            risk_pct=float(risk_pct),
            stop_distance_points=float(stop_distance),
            contract=contract,
            futures_capital_bucket=float(futures_bucket),
        )

        return {
            "ok": bool(result.ok),
            "reason": str(result.reason),
            "contracts": int(result.contracts),
            "margin_required": float(result.margin_required),
            "risk_per_contract": float(result.risk_per_contract),
            "total_risk": float(result.total_risk),
            "bucket_utilization_pct": float(result.bucket_utilization_pct),
        }


# ---------------------------
# State mutations (ExecutionGate relies on these)
# ---------------------------

def apply_trade(state: Dict[str, Any]) -> None:
    state["trades_today"] = _safe_int(state.get("trades_today"), 0) + 1


def apply_result(state: Dict[str, Any], *, instrument: str, pnl: float) -> None:
    pnl_f = _safe_float(pnl, 0.0)

    # daily pnl
    state["daily_pnl"] = _safe_float(state.get("daily_pnl"), 0.0) + pnl_f

    # equity peak tracking (best effort)
    eq = _safe_float(state.get("equity"), 0.0)
    peak = _safe_float(state.get("equity_peak"), eq)
    if eq > peak:
        state["equity_peak"] = eq

    # losses tracking
    if pnl_f < 0:
        state["consecutive_losses"] = _safe_int(state.get("consecutive_losses"), 0) + 1
        losses_by_pair = state.get("losses_by_pair") or {}
        if not isinstance(losses_by_pair, dict):
            losses_by_pair = {}
        losses_by_pair[instrument] = _safe_int(losses_by_pair.get(instrument), 0) + 1
        state["losses_by_pair"] = losses_by_pair
    else:
        state["consecutive_losses"] = 0

    # cooldown activation
    if _safe_int(state.get("consecutive_losses"), 0) >= MAX_CONSECUTIVE_LOSSES_BEFORE_COOLDOWN:
        state["cooldown_until"] = _iso(_utc_now() + timedelta(minutes=COOLDOWN_MINUTES))
