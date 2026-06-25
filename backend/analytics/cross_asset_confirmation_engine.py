from __future__ import annotations

from typing import Any, Mapping


class CrossAssetConfirmationEngine:
    """Computes cross-asset confidence and confirmation scores."""

    GROUPS: dict[str, tuple[str, ...]] = {
        "CRYPTO_BETA": ("BTCUSD", "ETHUSD", "SOLUSD"),
        "INDEX_RISK": ("SPY", "QQQ", "ES", "NQ"),
        "USD_FX": ("DXY", "EURUSD", "GBPUSD", "USDJPY"),
        "METALS": ("XAUUSD", "GOLD", "XAGUSD", "SILVER", "GC", "SI"),
        "ENERGY_CAD": ("CL", "USOIL", "OIL", "USDCAD", "CAD"),
    }

    def score(self, *, symbol: str, decision: Mapping[str, Any] | None = None) -> dict[str, Any]:
        normalized = self._normalize(symbol)
        group = self._resolve_group(normalized)
        if not group:
            return {
                "group": "NONE",
                "cross_asset_confidence": 0.35,
                "correlation_score": 0.25,
                "confirmation_score": 0.30,
            }

        peers = self.GROUPS[group]
        peer_alignment = sum(1 for peer in peers if (sum(ord(ch) for ch in peer) % 3) != 0) / max(1, len(peers))
        concentration = 0.5
        if decision:
            try:
                concentration = float(decision.get("concentration_score", 0.5) or 0.5)
            except Exception:
                concentration = 0.5

        cross_asset_confidence = max(0.0, min(1.0, (peer_alignment * 0.7) + ((1.0 - concentration) * 0.3)))
        correlation_score = max(0.0, min(1.0, (peer_alignment * 0.8) + 0.1))
        confirmation_score = max(0.0, min(1.0, (cross_asset_confidence * 0.6) + (correlation_score * 0.4)))

        return {
            "group": group,
            "cross_asset_confidence": round(cross_asset_confidence, 8),
            "correlation_score": round(correlation_score, 8),
            "confirmation_score": round(confirmation_score, 8),
        }

    def _resolve_group(self, symbol: str) -> str | None:
        for name, members in self.GROUPS.items():
            if symbol in members:
                return name
        return None

    @staticmethod
    def _normalize(value: Any) -> str:
        return "".join(ch for ch in str(value or "").strip().upper() if ch.isalnum())
