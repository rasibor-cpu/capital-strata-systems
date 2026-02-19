"""
Asset Allocator – Weekly Risk-Adjusted Rebalancing (Phase 1)
===========================================================

Capital Strata Systems (CSS)

Goal:
- Compute a weekly risk-adjusted score per instrument and asset_class
- Convert score -> allocation weight (multiplier)
- Apply at 50% intensity (per approved threshold scaling rule)
- Rebalance only on weekly boundaries (not per-trade)

Phase-1 Risk Proxy (Sharpe-lite):
    score = net_pnl / max(sum_abs_pnl, eps)

Where:
- net_pnl = sum(pnl)
- sum_abs_pnl = sum(abs(pnl))  (volatility proxy)

This is intentionally simple and deterministic. Later phases can swap
risk proxies (realized vol, downside dev, drawdown, etc).

Outputs:
- weight multipliers for {asset_class, instrument}
- diagnostics for logging/telemetry

Fail-closed:
- if no meaningful data -> neutral weight 1.0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional


EPS = 1e-9


@dataclass(frozen=True)
class AllocationResult:
    mode: str  # "WEEKLY"
    week_key: str
    applied_intensity: float  # 0.5 per current policy
    instrument_weights: Dict[str, float]
    asset_class_weights: Dict[str, float]
    diagnostics: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "week_key": self.week_key,
            "applied_intensity": self.applied_intensity,
            "instrument_weights": dict(self.instrument_weights),
            "asset_class_weights": dict(self.asset_class_weights),
            "diagnostics": dict(self.diagnostics),
        }


class AssetAllocator:
    """
    Weekly rebalancing allocator.

    Inputs expected from PerformanceLedger snapshot (best-effort):
    - weekly_instrument_totals: {instrument: pnl}
    - weekly_asset_totals: {asset_class: pnl}
    - weekly_instrument_abs_totals: {instrument: sum_abs_pnl}
    - weekly_asset_abs_totals: {asset_class: sum_abs_pnl}

    If abs totals are missing, we approximate abs proxy using abs(net_pnl),
    which is weaker but still deterministic.
    """

    def __init__(self, intensity: float = 0.5) -> None:
        # Per your instruction: start at 50% of approved thresholds
        self.intensity = float(intensity)

    # ------------------------------------------------------------
    # Core public API
    # ------------------------------------------------------------

    def rebalance_weekly(
        self,
        *,
        week_key: str,
        ledger_snapshot: Dict[str, Any],
    ) -> AllocationResult:
        """
        Compute weights using weekly aggregates ONLY.

        week_key: e.g. "2026-W07" (caller decides format)
        ledger_snapshot: PerformanceLedger.snapshot() dict (best-effort)
        """
        inst_net = _safe_dict(ledger_snapshot.get("weekly_instrument_totals"))
        asset_net = _safe_dict(ledger_snapshot.get("weekly_asset_totals"))

        inst_abs = _safe_dict(ledger_snapshot.get("weekly_instrument_abs_totals"))
        asset_abs = _safe_dict(ledger_snapshot.get("weekly_asset_abs_totals"))

        # Compute weights
        inst_weights, inst_diag = self._weights_from_totals(inst_net, inst_abs)
        asset_weights, asset_diag = self._weights_from_totals(asset_net, asset_abs)

        diagnostics = {
            "week_key": week_key,
            "instrument_diag": inst_diag,
            "asset_diag": asset_diag,
        }

        return AllocationResult(
            mode="WEEKLY",
            week_key=week_key,
            applied_intensity=self.intensity,
            instrument_weights=inst_weights,
            asset_class_weights=asset_weights,
            diagnostics=diagnostics,
        )

    # ------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------

    def _weights_from_totals(
        self,
        net_totals: Dict[str, float],
        abs_totals: Dict[str, float],
    ) -> tuple[Dict[str, float], Dict[str, Any]]:
        """
        net_totals: {key: net_pnl}
        abs_totals: {key: sum_abs_pnl} (optional)
        """
        weights: Dict[str, float] = {}
        scores: Dict[str, float] = {}

        if not net_totals:
            return {"__NEUTRAL__": 1.0}, {"note": "no_weekly_data", "scores": {}}

        for k, net in net_totals.items():
            net_f = float(net or 0.0)
            abs_proxy = float(abs_totals.get(k, 0.0) or 0.0)
            if abs_proxy <= 0:
                abs_proxy = abs(net_f)  # fallback proxy
            score = net_f / max(abs_proxy, EPS)
            scores[k] = score
            weights[k] = self._score_to_weight(score)

        diag = {
            "scores": scores,
            "min_score": min(scores.values()) if scores else 0.0,
            "max_score": max(scores.values()) if scores else 0.0,
            "avg_score": (sum(scores.values()) / len(scores)) if scores else 0.0,
        }
        return weights, diag

    def _score_to_weight(self, score: float) -> float:
        """
        Map risk-adjusted score -> target weight tier,
        then apply intensity scaling toward that target from neutral 1.0.

        Approved target tiers:
            score > 0.50 -> 1.25
            score > 0.25 -> 1.15
            score > 0.10 -> 1.05
            -0.10..0.10  -> 1.00
            score < -0.10 -> 0.85
            score < -0.25 -> 0.70

        Applied at 50% intensity:
            applied = 1.0 + (target - 1.0) * intensity
        """
        target = 1.0
        if score > 0.50:
            target = 1.25
        elif score > 0.25:
            target = 1.15
        elif score > 0.10:
            target = 1.05
        elif score < -0.25:
            target = 0.70
        elif score < -0.10:
            target = 0.85
        else:
            target = 1.00

        applied = 1.0 + (target - 1.0) * max(0.0, min(1.0, self.intensity))
        return float(applied)


def _safe_dict(x: Any) -> Dict[str, float]:
    if not isinstance(x, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in x.items():
        try:
            out[str(k)] = float(v)
        except Exception:
            out[str(k)] = 0.0
    return out
