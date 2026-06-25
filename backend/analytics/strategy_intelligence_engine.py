from __future__ import annotations

from typing import Any

from .strategy_memory_repository import StrategyMemoryRepository, StrategyMemoryRepositoryError


class StrategyIntelligenceEngineError(RuntimeError):
    """Fail-closed exception for strategy intelligence operations."""


class StrategyIntelligenceEngine:
    """Context-aware strategy ranking using persisted strategy memory records."""

    def __init__(self, repository: StrategyMemoryRepository) -> None:
        self.repository = repository

    def rank_strategies_by_context(
        self,
        *,
        symbol: str | None = None,
        asset_class: str | None = None,
        market_regime: str | None = None,
        session: str | None = None,
    ) -> list[dict[str, Any]]:
        records = self._load_filtered_records(
            symbol=symbol,
            asset_class=asset_class,
            market_regime=market_regime,
            session=session,
        )
        if not records:
            return []

        buckets: dict[str, dict[str, Any]] = {}
        for row in records:
            strategy_id = row["strategy_id"]
            entry = buckets.setdefault(
                strategy_id,
                {
                    "strategy_id": strategy_id,
                    "trade_count": 0,
                    "win_count": 0,
                    "realized_pnl": 0.0,
                    "confidence_total": 0.0,
                },
            )
            entry["trade_count"] += 1
            entry["win_count"] += 1 if bool(row["win"]) else 0
            entry["realized_pnl"] += float(row["realized_pnl"])
            entry["confidence_total"] += float(row["confidence"])

        ranked: list[dict[str, Any]] = []
        for strategy_id in sorted(buckets.keys()):
            item = buckets[strategy_id]
            trade_count = int(item["trade_count"])
            win_rate = item["win_count"] / trade_count
            avg_confidence = item["confidence_total"] / trade_count
            average_pnl = item["realized_pnl"] / trade_count
            ranked.append(
                {
                    "strategy_id": strategy_id,
                    "trade_count": trade_count,
                    "realized_pnl": float(item["realized_pnl"]),
                    "average_pnl": float(average_pnl),
                    "win_rate": float(win_rate),
                    "confidence": float(avg_confidence),
                    "ranking_score": float((average_pnl * 0.6) + (win_rate * 0.3) + (avg_confidence * 0.1)),
                }
            )

        ranked.sort(
            key=lambda row: (
                row["ranking_score"],
                row["realized_pnl"],
                row["win_rate"],
                row["strategy_id"],
            ),
            reverse=True,
        )

        return ranked

    def best_strategy_for_symbol(self, symbol: str) -> dict[str, Any] | None:
        ranked = self.rank_strategies_by_context(symbol=symbol)
        return ranked[0] if ranked else None

    def best_strategy_for_regime(self, market_regime: str) -> dict[str, Any] | None:
        ranked = self.rank_strategies_by_context(market_regime=market_regime)
        return ranked[0] if ranked else None

    def strategy_confidence(
        self,
        strategy_id: str,
        *,
        symbol: str | None = None,
        market_regime: str | None = None,
        session: str | None = None,
    ) -> float:
        target_strategy = str(strategy_id or "").strip()
        if not target_strategy:
            raise StrategyIntelligenceEngineError("strategy_id must be non-empty")

        records = self._load_filtered_records(
            symbol=symbol,
            asset_class=None,
            market_regime=market_regime,
            session=session,
        )

        matched = [row for row in records if row["strategy_id"] == target_strategy]
        if not matched:
            return 0.0

        return float(sum(float(row["confidence"]) for row in matched) / len(matched))

    def strategy_memory_summary(self) -> dict[str, Any]:
        records = self._load_filtered_records(
            symbol=None,
            asset_class=None,
            market_regime=None,
            session=None,
        )
        if not records:
            return {}

        unique_strategies = sorted({row["strategy_id"] for row in records})
        realized_pnl = sum(float(row["realized_pnl"]) for row in records)
        win_count = sum(1 for row in records if bool(row["win"]))

        return {
            "record_count": len(records),
            "strategy_count": len(unique_strategies),
            "strategies": unique_strategies,
            "realized_pnl": float(realized_pnl),
            "win_rate": float(win_count / len(records)),
        }

    def _load_filtered_records(
        self,
        *,
        symbol: str | None,
        asset_class: str | None,
        market_regime: str | None,
        session: str | None,
    ) -> list[dict[str, Any]]:
        try:
            rows = self.repository.load_records()
        except StrategyMemoryRepositoryError as exc:
            raise StrategyIntelligenceEngineError(str(exc)) from exc

        symbol_filter = self._normalize_optional(symbol, upper=True)
        asset_filter = self._normalize_optional(asset_class, upper=True)
        regime_filter = self._normalize_optional(market_regime, upper=True)
        session_filter = self._normalize_optional(session, upper=False)

        if symbol is not None and symbol_filter is None:
            raise StrategyIntelligenceEngineError("symbol must be non-empty when provided")
        if asset_class is not None and asset_filter is None:
            raise StrategyIntelligenceEngineError("asset_class must be non-empty when provided")
        if market_regime is not None and regime_filter is None:
            raise StrategyIntelligenceEngineError("market_regime must be non-empty when provided")
        if session is not None and session_filter is None:
            raise StrategyIntelligenceEngineError("session must be non-empty when provided")

        filtered = rows
        if symbol_filter is not None:
            filtered = [row for row in filtered if row["symbol"] == symbol_filter]
        if asset_filter is not None:
            filtered = [row for row in filtered if row["asset_class"] == asset_filter]
        if regime_filter is not None:
            filtered = [row for row in filtered if row["market_regime"] == regime_filter]
        if session_filter is not None:
            filtered = [row for row in filtered if row["session"] == session_filter]

        return filtered

    @staticmethod
    def _normalize_optional(value: str | None, *, upper: bool) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return normalized.upper() if upper else normalized
