from __future__ import annotations

from typing import List, Dict, Any


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(v, hi))


class CapitalAllocator:
    """
    CSS Capital Allocator

    Backward-compatible superset of the earlier allocator.

    Preserved behavior:
    - converts ranked opportunity results into capital allocations
    - uses total_capital and max_positions
    - supports spread-aware damping
    - proportional allocation across selected candidates

    New behavior:
    - supports both older and newer scoring fields
    - incorporates intelligence fields:
        * vwap_dev
        * momentum
        * velocity
        * mean_reversion_score
        * pressure_score
        * confluence_score
    - remains lightweight and safe for live dashboard use
    """

    def __init__(self, total_capital: float, max_positions: int = 5) -> None:
        self.total_capital = float(total_capital)
        self.max_positions = int(max_positions)

    def _base_weight(self, ai_score: float) -> float:
        """
        Convert AI score into a base weight.

        Supports either:
        - legacy 0-100 scale
        - modern 0-1 scale
        """
        if ai_score <= 1.0:
            ai_score = ai_score * 100.0

        if ai_score >= 90:
            return 1.0
        if ai_score >= 80:
            return 0.8
        if ai_score >= 70:
            return 0.6
        if ai_score >= 60:
            return 0.4
        return 0.0

    def _symbol_key(self, row: Dict[str, Any]) -> str:
        return str(row.get("symbol") or row.get("asset") or "").upper()

    def _build_market_lookup(self, market_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        lookup: Dict[str, Dict[str, Any]] = {}
        for r in market_rows:
            key = self._symbol_key(r)
            if key:
                lookup[key] = r
        return lookup

    def _intelligence_boost(self, row: Dict[str, Any]) -> float:
        """
        Convert intelligence fields into a modest additive multiplier.

        Kept intentionally conservative so this enhances allocation
        without overpowering the base AI score model.
        """
        vwap_dev = abs(_safe_float(row.get("vwap_dev", 0.0)))
        momentum = abs(_safe_float(row.get("momentum", 0.0)))
        velocity = abs(_safe_float(row.get("velocity", 0.0)))
        mean_rev = _safe_float(row.get("mean_reversion_score", 0.0))
        pressure = _safe_float(row.get("pressure_score", 0.0))
        confluence = _safe_float(row.get("confluence_score", 0.0))

        # Conservative normalized contributions
        vwap_component = _clamp(vwap_dev * 8.0, 0.0, 0.25)
        momentum_component = _clamp(momentum * 40.0, 0.0, 0.15)
        velocity_component = _clamp(velocity * 40.0, 0.0, 0.10)
        mean_rev_component = _clamp(mean_rev, 0.0, 1.0) * 0.20
        pressure_component = _clamp(pressure, 0.0, 1.0) * 0.15
        confluence_component = _clamp(confluence, 0.0, 1.0) * 0.15

        boost = (
            vwap_component
            + momentum_component
            + velocity_component
            + mean_rev_component
            + pressure_component
            + confluence_component
        )

        # Final multiplier remains modest and governed
        return 1.0 + _clamp(boost, 0.0, 0.60)

    def _spread_dampener(self, spread_bps: float) -> float:
        spread = abs(_safe_float(spread_bps, 0.0))

        if spread > 500:
            return 0.4
        if spread > 300:
            return 0.6
        if spread > 150:
            return 0.8
        return 1.0

    def allocate(
        self,
        ai_results: List[Dict[str, Any]],
        market_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Returns proportional capital allocations for selected candidates.

        Compatible with:
        - older ai_results using 'opportunity_score'
        - newer ranked results using 'score'
        - market rows keyed by either 'asset' or 'symbol'
        """
        rows_by_symbol = self._build_market_lookup(market_rows)

        candidates: List[Dict[str, Any]] = []

        for item in ai_results:
            symbol = str(item.get("symbol", "")).upper()
            if not symbol:
                continue

            if symbol not in rows_by_symbol:
                continue

            row = rows_by_symbol[symbol]

            ai_score = _safe_float(
                item.get("opportunity_score", item.get("score", 0.0)),
                0.0,
            )

            base = self._base_weight(ai_score)
            if base == 0.0:
                continue

            spread_bps = _safe_float(row.get("spread_bps", 0.0), 0.0)
            vol_adj = self._spread_dampener(spread_bps)
            intel_boost = self._intelligence_boost(row)

            weight = base * vol_adj * intel_boost

            candidates.append(
                {
                    "symbol": symbol,
                    "score": ai_score,
                    "weight": weight,
                    "spread_bps": spread_bps,
                    "vwap_dev": _safe_float(row.get("vwap_dev", 0.0), 0.0),
                    "momentum": _safe_float(row.get("momentum", 0.0), 0.0),
                    "velocity": _safe_float(row.get("velocity", 0.0), 0.0),
                    "mean_reversion_score": _safe_float(row.get("mean_reversion_score", 0.0), 0.0),
                    "pressure_score": _safe_float(row.get("pressure_score", 0.0), 0.0),
                    "confluence_score": _safe_float(row.get("confluence_score", 0.0), 0.0),
                }
            )

        candidates.sort(key=lambda x: x["weight"], reverse=True)
        candidates = candidates[: self.max_positions]

        total_weight = sum(_safe_float(c.get("weight"), 0.0) for c in candidates)
        if total_weight <= 0:
            return []

        allocations: List[Dict[str, Any]] = []

        for c in candidates:
            capital = (_safe_float(c["weight"]) / total_weight) * self.total_capital

            allocations.append(
                {
                    "symbol": c["symbol"],
                    "ai_score": round(_safe_float(c["score"]), 6),
                    "capital": round(capital, 2),
                    "weight": round(_safe_float(c["weight"]), 6),
                    "spread_bps": round(_safe_float(c["spread_bps"]), 6),
                    "vwap_dev": round(_safe_float(c["vwap_dev"]), 6),
                    "momentum": round(_safe_float(c["momentum"]), 6),
                    "velocity": round(_safe_float(c["velocity"]), 6),
                    "mean_reversion_score": round(_safe_float(c["mean_reversion_score"]), 6),
                    "pressure_score": round(_safe_float(c["pressure_score"]), 6),
                    "confluence_score": round(_safe_float(c["confluence_score"]), 6),
                }
            )

        return allocations