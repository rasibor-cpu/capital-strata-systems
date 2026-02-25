"""
engine/portfolio/portfolio_capital_controller.py

PortfolioCapitalController (PCC)
--------------------------------
Institutional portfolio-level capital governance layer.

Adds:
- Statistical correlation throttle (avg abs correlation vs open positions in same asset class)

Notes:
- PCC remains stateless: caller supplies exposures.
- Fail-closed: unknown asset_class will BLOCK unless allow_unknown_asset_class=True
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


# =========================
# Decision Object
# =========================

@dataclass(frozen=True)
class PCCDecision:
    final: str  # "ALLOW" | "BLOCK"
    reason: str
    sizing_multiplier: float  # 0.0 if blocked; otherwise <= 1.0


# =========================
# Proposal Input
# =========================

@dataclass(frozen=True)
class TradeProposal:
    """
    Inputs required for portfolio governance.

    Required:
      - instrument
      - asset_class
      - requested_notional

    Required portfolio state:
      - equity
      - current_total_exposure
      - current_instrument_exposure
      - current_asset_class_exposure
      - portfolio_dd_pct

    Optional:
      - open_positions_in_asset_class (count)
      - avg_correlation: average absolute correlation vs open positions (0.0..1.0)
    """
    instrument: str
    asset_class: str
    requested_notional: float

    equity: float
    current_total_exposure: float
    current_instrument_exposure: float
    current_asset_class_exposure: float
    portfolio_dd_pct: float

    open_positions_in_asset_class: int = 0
    avg_correlation: float = 0.0


# =========================
# Controller
# =========================

class PortfolioCapitalController:
    """
    Portfolio-level exposure + drawdown + correlation governance.

    Default policy:
      - Global max exposure = 40% of equity
      - Instrument cap = 8% of equity
      - Asset-class caps (% of equity):
          FX: 30%
          FUTURES: 20%
          COMMODITIES: 15%
          EQUITIES: 20%
          CRYPTO: 10%
      - Drawdown throttles:
          DD >= 5%  -> sizing *= 0.50
          DD >= 8%  -> BLOCK new trades
          DD >= 12% -> BLOCK new trades
      - Correlation throttle (avg abs correlation vs open positions in same asset class):
          > 0.80 -> BLOCK
          > 0.60 -> sizing *= 0.65
          > 0.30 -> sizing *= 0.85
    """

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"

    def __init__(
        self,
        *,
        max_global_exposure_pct: float = 0.40,
        default_instrument_cap_pct: float = 0.08,
        instrument_caps_pct: Optional[Dict[str, float]] = None,
        asset_class_caps_pct: Optional[Dict[str, float]] = None,
        dd_soft_throttle_pct: float = 5.0,
        dd_hard_block_pct: float = 8.0,
        dd_force_flatten_pct: float = 12.0,
        dd_soft_multiplier: float = 0.50,
        allow_unknown_asset_class: bool = False,
        # Correlation policy
        corr_mid: float = 0.30,
        corr_high: float = 0.60,
        corr_block: float = 0.80,
        corr_mid_multiplier: float = 0.85,
        corr_high_multiplier: float = 0.65,
    ) -> None:
        self.max_global_exposure_pct = float(max_global_exposure_pct)
        self.default_instrument_cap_pct = float(default_instrument_cap_pct)

        self.instrument_caps_pct = dict(instrument_caps_pct or {})

        self.asset_class_caps_pct = dict(
            asset_class_caps_pct
            or {
                "FX": 0.30,
                "FUTURES": 0.20,
                "COMMODITIES": 0.15,
                "EQUITIES": 0.20,
                "CRYPTO": 0.10,
            }
        )

        self.dd_soft_throttle_pct = float(dd_soft_throttle_pct)
        self.dd_hard_block_pct = float(dd_hard_block_pct)
        self.dd_force_flatten_pct = float(dd_force_flatten_pct)
        self.dd_soft_multiplier = float(dd_soft_multiplier)

        self.allow_unknown_asset_class = bool(allow_unknown_asset_class)

        # Correlation thresholds/multipliers
        self.corr_mid = float(corr_mid)
        self.corr_high = float(corr_high)
        self.corr_block = float(corr_block)
        self.corr_mid_multiplier = float(corr_mid_multiplier)
        self.corr_high_multiplier = float(corr_high_multiplier)

        self._validate_policy()

    # =========================
    # Public API
    # =========================

    def evaluate(self, proposal: TradeProposal) -> PCCDecision:
        ok, reason = self._validate_inputs(proposal)
        if not ok:
            return PCCDecision(self.BLOCK, reason, 0.0)

        equity = float(proposal.equity)
        if equity <= 0:
            return PCCDecision(self.BLOCK, "EQUITY_INVALID", 0.0)

        sizing_multiplier = 1.0

        # 1) Drawdown gating/throttle
        dd_mult, dd_final, dd_reason = self._apply_drawdown_policy(float(proposal.portfolio_dd_pct))
        if dd_final == self.BLOCK:
            return PCCDecision(self.BLOCK, dd_reason, 0.0)
        sizing_multiplier *= dd_mult

        # 2) Statistical correlation throttle
        #    avg_correlation is expected in [0,1]. If it’s 0, treat as "unknown/low".
        avg_corr = float(getattr(proposal, "avg_correlation", 0.0) or 0.0)

        if avg_corr > self.corr_block:
            return PCCDecision(self.BLOCK, "HIGH_CORRELATION_BLOCK", 0.0)
        elif avg_corr > self.corr_high:
            sizing_multiplier *= self.corr_high_multiplier
        elif avg_corr > self.corr_mid:
            sizing_multiplier *= self.corr_mid_multiplier

        # 3) Exposure caps
        final, reason = self._check_exposure_caps(proposal, sizing_multiplier)
        if final == self.BLOCK:
            return PCCDecision(self.BLOCK, reason, 0.0)

        sizing_multiplier = max(0.0, min(1.0, float(sizing_multiplier)))
        return PCCDecision(self.ALLOW, "OK", sizing_multiplier)

    def get_instrument_cap_pct(self, instrument: str) -> float:
        return float(self.instrument_caps_pct.get(instrument, self.default_instrument_cap_pct))

    def get_asset_class_cap_pct(self, asset_class: str) -> Optional[float]:
        if asset_class in self.asset_class_caps_pct:
            return float(self.asset_class_caps_pct[asset_class])
        return None

    # =========================
    # Internals
    # =========================

    def _validate_policy(self) -> None:
        if not (0.0 < self.max_global_exposure_pct <= 1.0):
            raise ValueError("max_global_exposure_pct must be in (0, 1].")
        if not (0.0 < self.default_instrument_cap_pct <= 1.0):
            raise ValueError("default_instrument_cap_pct must be in (0, 1].")

        for k, v in self.instrument_caps_pct.items():
            if not (0.0 < float(v) <= 1.0):
                raise ValueError(f"instrument_caps_pct[{k}] must be in (0, 1].")

        for k, v in self.asset_class_caps_pct.items():
            if not (0.0 < float(v) <= 1.0):
                raise ValueError(f"asset_class_caps_pct[{k}] must be in (0, 1].")

        if self.dd_soft_throttle_pct < 0 or self.dd_hard_block_pct < 0 or self.dd_force_flatten_pct < 0:
            raise ValueError("drawdown thresholds must be >= 0.")
        if not (0.0 < self.dd_soft_multiplier <= 1.0):
            raise ValueError("dd_soft_multiplier must be in (0, 1].")
        if self.dd_soft_throttle_pct > self.dd_hard_block_pct:
            raise ValueError("dd_soft_throttle_pct must be <= dd_hard_block_pct.")
        if self.dd_hard_block_pct > self.dd_force_flatten_pct:
            raise ValueError("dd_hard_block_pct must be <= dd_force_flatten_pct.")

        # Correlation constraints
        for name, v in [
            ("corr_mid", self.corr_mid),
            ("corr_high", self.corr_high),
            ("corr_block", self.corr_block),
        ]:
            if not (0.0 <= float(v) <= 1.0):
                raise ValueError(f"{name} must be in [0,1].")

        for name, v in [
            ("corr_mid_multiplier", self.corr_mid_multiplier),
            ("corr_high_multiplier", self.corr_high_multiplier),
        ]:
            if not (0.0 < float(v) <= 1.0):
                raise ValueError(f"{name} must be in (0,1].")

    def _validate_inputs(self, p: TradeProposal) -> Tuple[bool, str]:
        if not p.instrument or not isinstance(p.instrument, str):
            return False, "INSTRUMENT_MISSING"
        if not p.asset_class or not isinstance(p.asset_class, str):
            return False, "ASSET_CLASS_MISSING"
        if float(p.requested_notional) <= 0:
            return False, "REQUESTED_NOTIONAL_INVALID"

        if p.equity is None or float(p.equity) <= 0:
            return False, "EQUITY_INVALID"
        if float(p.current_total_exposure) < 0:
            return False, "TOTAL_EXPOSURE_INVALID"
        if float(p.current_instrument_exposure) < 0:
            return False, "INSTRUMENT_EXPOSURE_INVALID"
        if float(p.current_asset_class_exposure) < 0:
            return False, "ASSET_CLASS_EXPOSURE_INVALID"
        if float(p.portfolio_dd_pct) < 0:
            return False, "DD_INVALID"
        if int(p.open_positions_in_asset_class) < 0:
            return False, "OPEN_POSITIONS_INVALID"

        avg_corr = float(getattr(p, "avg_correlation", 0.0) or 0.0)
        if avg_corr < 0.0 or avg_corr > 1.0:
            return False, "AVG_CORRELATION_INVALID"

        if p.asset_class not in self.asset_class_caps_pct and not self.allow_unknown_asset_class:
            return False, "ASSET_CLASS_UNKNOWN_FAIL_CLOSED"

        return True, "OK"

    def _apply_drawdown_policy(self, dd_pct: float) -> Tuple[float, str, str]:
        if dd_pct >= self.dd_force_flatten_pct:
            return 0.0, self.BLOCK, "DD_FORCE_FLATTEN_BLOCK"
        if dd_pct >= self.dd_hard_block_pct:
            return 0.0, self.BLOCK, "DD_HARD_BLOCK"

        if dd_pct >= self.dd_soft_throttle_pct:
            return self.dd_soft_multiplier, self.ALLOW, "DD_SOFT_THROTTLE"

        return 1.0, self.ALLOW, "DD_OK"

    def _check_exposure_caps(self, p: TradeProposal, sizing_multiplier: float) -> Tuple[str, str]:
        effective_notional = float(p.requested_notional) * float(sizing_multiplier)
        equity = float(p.equity)

        # Global cap
        global_cap = equity * self.max_global_exposure_pct
        post_global = float(p.current_total_exposure) + effective_notional
        if post_global > global_cap + 1e-9:
            return self.BLOCK, "GLOBAL_EXPOSURE_CAP"

        # Instrument cap
        inst_cap_pct = self.get_instrument_cap_pct(p.instrument)
        inst_cap = equity * inst_cap_pct
        post_inst = float(p.current_instrument_exposure) + effective_notional
        if post_inst > inst_cap + 1e-9:
            return self.BLOCK, "INSTRUMENT_EXPOSURE_CAP"

        # Asset class cap
        ac_cap_pct = self.get_asset_class_cap_pct(p.asset_class)
        if ac_cap_pct is None:
            return self.ALLOW, "ASSET_CLASS_NO_CAP"

        ac_cap = equity * float(ac_cap_pct)
        post_ac = float(p.current_asset_class_exposure) + effective_notional
        if post_ac > ac_cap + 1e-9:
            return self.BLOCK, "ASSET_CLASS_EXPOSURE_CAP"

        return self.ALLOW, "OK"