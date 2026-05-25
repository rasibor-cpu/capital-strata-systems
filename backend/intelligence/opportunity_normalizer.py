from __future__ import annotations

from typing import Any, Dict

from backend.intelligence.unified_opportunity import UnifiedOpportunity


class OpportunityNormalizer:
    def normalize_candidate(self, asset_class: str, payload: Dict[str, Any] | None) -> UnifiedOpportunity:
        payload = payload if isinstance(payload, dict) else {}
        cls = str(asset_class or payload.get("asset_class", "generic")).lower()
        dispatch = {
            "crypto": self.normalize_crypto_candidate,
            "fx": self.normalize_fx_candidate,
            "forex": self.normalize_fx_candidate,
            "futures": self.normalize_futures_candidate,
            "options": self.normalize_options_candidate,
            "equity": self.normalize_equity_candidate,
            "equities": self.normalize_equity_candidate,
            "etf": self.normalize_equity_candidate,
            "indices": self.normalize_generic_candidate,
            "index": self.normalize_generic_candidate,
            "commodities": self.normalize_generic_candidate,
            "commodity": self.normalize_generic_candidate,
        }
        normalizer = dispatch.get(cls, self.normalize_generic_candidate)
        try:
            return normalizer(payload)
        except Exception:
            return self.normalize_generic_candidate(payload)

    def normalize_crypto_candidate(self, payload: Dict[str, Any]) -> UnifiedOpportunity:
        return self._normalize(payload, "crypto")

    def normalize_fx_candidate(self, payload: Dict[str, Any]) -> UnifiedOpportunity:
        return self._normalize(payload, "fx")

    def normalize_futures_candidate(self, payload: Dict[str, Any]) -> UnifiedOpportunity:
        return self._normalize(payload, "futures")

    def normalize_options_candidate(self, payload: Dict[str, Any]) -> UnifiedOpportunity:
        return self._normalize(payload, "options")

    def normalize_equity_candidate(self, payload: Dict[str, Any]) -> UnifiedOpportunity:
        return self._normalize(payload, "equity")

    def normalize_generic_candidate(self, payload: Dict[str, Any]) -> UnifiedOpportunity:
        return self._normalize(payload, str(payload.get("asset_class", "generic")).lower())

    def _normalize(self, payload: Dict[str, Any], asset_class: str) -> UnifiedOpportunity:
        symbol = str(payload.get("symbol", payload.get("instrument", "UNKNOWN")))
        signal_strength = self._safe_float(payload.get("scanner_score", payload.get("signal_strength", payload.get("score", 0.0))))
        confidence = self._safe_float(payload.get("confidence", signal_strength))
        spread_score = self._safe_float(payload.get("spread_bps", payload.get("spread_score", payload.get("spread_pct", 0.0))))
        volatility = self._safe_float(payload.get("volatility_pct", payload.get("volatility_score", 0.0)))
        liquidity = self._safe_float(payload.get("liquidity_score", payload.get("volume_24h", payload.get("avg_volume_24h", 0.0))))
        expected_edge = self._safe_float(payload.get("expected_edge", payload.get("edge", signal_strength - spread_score)))
        est_cost = self._safe_float(payload.get("estimated_cost", payload.get("cost_bps", payload.get("estimated_cost_bps", 0.0))))
        est_slippage = self._safe_float(payload.get("estimated_slippage", payload.get("slippage_bps", 0.0)))

        direction = str(payload.get("direction", payload.get("bias", "neutral"))).lower()
        execution_viable = bool(payload.get("execution_viable", False))

        metadata = {
            "raw_payload_keys": sorted(payload.keys()),
            "normalization_version": "phase56a",
        }

        return UnifiedOpportunity(
            symbol=symbol,
            asset_class=asset_class,
            venue=str(payload.get("venue", payload.get("exchange", "UNKNOWN"))),
            direction=direction,
            signal_strength=signal_strength,
            confidence=confidence,
            expected_edge=expected_edge,
            estimated_cost=est_cost,
            estimated_slippage=est_slippage,
            liquidity_score=liquidity,
            volatility_score=volatility,
            spread_score=spread_score,
            execution_viable=execution_viable,
            scanner_source=str(payload.get("source", payload.get("scanner_source", "unknown"))),
            timestamp=str(payload.get("timestamp", payload.get("time", UnifiedOpportunity().timestamp))),
            metadata=metadata,
        )

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default
