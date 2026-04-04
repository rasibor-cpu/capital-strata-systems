from __future__ import annotations

from typing import Any, Dict, List


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
    Live-dashboard scaled version.

    Preserves:
    - allocate(ai_results, market_rows)
    - max_positions
    - spread-aware damping
    - proportional allocation

    Fixes:
    - supports current 0-1 score range from the dashboard
    - avoids zero-allocation deadlock when signals are WATCH/QUALIFIED
    """

    def __init__(self, total_capital: float, max_positions: int = 5) -> None:
        self.total_capital = float(total_capital)
        self.max_positions = int(max_positions)

    def _symbol_key(self, row: Dict[str, Any]) -> str:
        return str(row.get("symbol") or row.get("asset") or "").upper()

    def _build_market_lookup(self, market_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        lookup: Dict[str, Dict[str, Any]] = {}
        for r in market_rows:
            key = self._symbol_key(r)
            if key:
                lookup[key] = r
        return lookup

    def _base_weight(self, ai_score: float) -> float:
        """
        Supports both:
        - modern 0-1 scale
        - legacy 0-100 scale
        """
        score = _safe_float(ai_score, 0.0)

        if score <= 1.0:
            # Current dashboard scores are roughly 0.08 to 0.22
            if score >= 0.22:
                return 1.00
            if score >= 0.18:
                return 0.85
            if score >= 0.15:
                return 0.70
            if score >= 0.12:
                return 0.55
            if score >= 0.09:
                return 0.40
            if score >= 0.06:
                return 0.25
            return 0.0

        # Legacy 0-100 scale
        if score >= 90:
            return 1.00
        if score >= 80:
            return 0.80
        if score >= 70:
            return 0.60
        if score >= 60:
            return 0.40
        if score >= 50:
            return 0.25
        return 0.0

    def _intelligence_boost(self, row: Dict[str, Any]) -> float:
        vwap_dev = abs(_safe_float(row.get("vwap_dev", 0.0)))
        momentum = abs(_safe_float(row.get("momentum", row.get("momentum_window", 0.0))))
        velocity = abs(_safe_float(row.get("velocity", 0.0)))
        mean_rev = _safe_float(row.get("mean_reversion_score", 0.0))
        pressure = _safe_float(row.get("pressure_score", 0.0))
        confluence = _safe_float(row.get("confluence_score", 0.0))
        trade_score = _safe_float(row.get("trade_score", 0.0))

        vwap_component = _clamp(vwap_dev * 10.0, 0.0, 0.20)
        momentum_component = _clamp(momentum * 25.0, 0.0, 0.10)
        velocity_component = _clamp(velocity * 25.0, 0.0, 0.08)
        mean_rev_component = _clamp(mean_rev, 0.0, 1.0) * 0.10
        pressure_component = _clamp(pressure, 0.0, 1.0) * 0.10
        confluence_component = _clamp(confluence, 0.0, 1.0) * 0.10
        trade_score_component = _clamp(trade_score * 2.5, 0.0, 0.22)

        boost = (
            vwap_component
            + momentum_component
            + velocity_component
            + mean_rev_component
            + pressure_component
            + confluence_component
            + trade_score_component
        )

        return 1.0 + _clamp(boost, 0.0, 0.60)

    def _spread_dampener(self, spread_bps: float) -> float:
        spread = abs(_safe_float(spread_bps, 0.0))

        if spread > 25:
            return 0.55
        if spread > 18:
            return 0.70
        if spread > 12:
            return 0.82
        if spread > 8:
            return 0.92
        return 1.0

    def allocate(
        self,
        ai_results: List[Dict[str, Any]],
        market_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
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
                item.get("trade_score", item.get("opportunity_score", item.get("score", 0.0))),
                0.0,
            )

            base = self._base_weight(ai_score)
            if base == 0.0:
                continue

            spread_bps = _safe_float(row.get("spread_bps", item.get("spread_bps", 0.0)), 0.0)
            vol_adj = self._spread_dampener(spread_bps)
            intel_boost = self._intelligence_boost({**row, **item})

            weight = base * vol_adj * intel_boost

            merged = {**row, **item}

            candidates.append(
                {
                    "symbol": symbol,
                    "score": ai_score,
                    "weight": weight,
                    "capital_hint": merged.get("capital"),
                    "spread_bps": spread_bps,
                    "vwap_dev": _safe_float(merged.get("vwap_dev", 0.0), 0.0),
                    "momentum": _safe_float(merged.get("momentum", merged.get("momentum_window", 0.0)), 0.0),
                    "velocity": _safe_float(merged.get("velocity", 0.0), 0.0),
                    "mean_reversion_score": _safe_float(merged.get("mean_reversion_score", 0.0), 0.0),
                    "pressure_score": _safe_float(merged.get("pressure_score", 0.0), 0.0),
                    "confluence_score": _safe_float(merged.get("confluence_score", 0.0), 0.0),
                    "trade_score": _safe_float(merged.get("trade_score", 0.0), 0.0),
                    "asset_class": merged.get("asset_class", ""),
                    "price": _safe_float(merged.get("price", 0.0), 0.0),
                    "vwap": _safe_float(merged.get("vwap", 0.0), 0.0),
                    "signal_tier": merged.get("signal_tier", ""),
                    "decision": merged.get("decision", ""),
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
                    "trade_score": round(_safe_float(c["trade_score"]), 6),
                    "capital": round(capital, 2),
                    "weight": round(_safe_float(c["weight"]), 6),
                    "spread_bps": round(_safe_float(c["spread_bps"]), 6),
                    "vwap_dev": round(_safe_float(c["vwap_dev"]), 6),
                    "momentum": round(_safe_float(c["momentum"]), 6),
                    "velocity": round(_safe_float(c["velocity"]), 6),
                    "mean_reversion_score": round(_safe_float(c["mean_reversion_score"]), 6),
                    "pressure_score": round(_safe_float(c["pressure_score"]), 6),
                    "confluence_score": round(_safe_float(c["confluence_score"]), 6),
                    "asset_class": c.get("asset_class", ""),
                    "price": round(_safe_float(c["price"]), 8),
                    "vwap": round(_safe_float(c["vwap"]), 8),
                    "signal_tier": c.get("signal_tier", ""),
                    "decision": c.get("decision", ""),
                }
            )

        return allocations