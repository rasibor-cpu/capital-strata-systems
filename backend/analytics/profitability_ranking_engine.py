from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal

from .trade_outcome_repository import TradeOutcomeRepository, TradeOutcomeRepositoryError


class ProfitabilityRankingEngineError(RuntimeError):
    """Explicit fail-closed exception for profitability ranking failures."""


GroupField = Literal["symbol", "asset_class", "strategy_id"]


@dataclass(frozen=True)
class RankingPolicy:
    """Confidence and restriction policy for profitability rankings."""

    minimum_trade_count: int = 3
    restricted_score_threshold: float = 0.0


class ProfitabilityRankingEngine:
    """Rank realized profitability from the Phase 128A trade outcome warehouse."""

    def __init__(
        self,
        repository: TradeOutcomeRepository,
        *,
        minimum_trade_count: int = 3,
        restricted_score_threshold: float = 0.0,
    ):
        if minimum_trade_count <= 0:
            raise ProfitabilityRankingEngineError("minimum_trade_count must be positive")
        self.repository = repository
        self.policy = RankingPolicy(
            minimum_trade_count=minimum_trade_count,
            restricted_score_threshold=float(restricted_score_threshold),
        )

    def rank_symbols(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        return self._rank("symbol", limit=limit)

    def rank_asset_classes(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        return self._rank("asset_class", limit=limit)

    def rank_strategies(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        return self._rank("strategy_id", limit=limit)

    def preferred_symbols(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        ranked = [
            row
            for row in self.rank_symbols()
            if row["trade_count"] >= self.policy.minimum_trade_count and row["score"] > 0.0
        ]
        return self._apply_limit(ranked, limit)

    def restricted_symbols(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        ranked = [
            row
            for row in self.rank_symbols()
            if row["trade_count"] < self.policy.minimum_trade_count
            or row["score"] <= self.policy.restricted_score_threshold
        ]
        restricted_first = sorted(ranked, key=lambda row: (row["score"], row["realized_pnl"], row["symbol"]))
        return self._apply_limit(restricted_first, limit)

    def _rank(self, field: GroupField, *, limit: int | None) -> list[dict[str, Any]]:
        rows = self._build_rows(field)
        ranked = sorted(
            rows,
            key=lambda row: (row["score"], row["realized_pnl"], row["win_rate"], row[field]),
            reverse=True,
        )
        return self._apply_limit(ranked, limit)

    def _build_rows(self, field: GroupField) -> list[dict[str, Any]]:
        groups: dict[str, list[float]] = defaultdict(list)
        try:
            outcomes = self.repository.load_outcomes()
        except TradeOutcomeRepositoryError as exc:
            raise ProfitabilityRankingEngineError(f"Unable to rank invalid trade outcome warehouse: {exc}") from exc

        for outcome in outcomes:
            try:
                key = str(outcome[field]).strip()
                pnl = float(outcome["realized_pnl"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ProfitabilityRankingEngineError("Trade outcome warehouse contains invalid ranking data") from exc
            if not key:
                raise ProfitabilityRankingEngineError(f"Trade outcome field {field} must be non-empty")
            groups[key].append(pnl)

        return [self._metrics(field, key, pnls) for key, pnls in groups.items()]

    def _metrics(self, field: GroupField, key: str, pnls: list[float]) -> dict[str, Any]:
        trade_count = len(pnls)
        if trade_count <= 0:
            raise ProfitabilityRankingEngineError("Cannot rank an empty profitability group")

        realized_pnl = sum(pnls)
        win_count = sum(1 for pnl in pnls if pnl > 0.0)
        loss_count = sum(1 for pnl in pnls if pnl < 0.0)
        win_rate = win_count / trade_count
        average_pnl = realized_pnl / trade_count
        confidence = min(trade_count / self.policy.minimum_trade_count, 1.0)
        score = ((realized_pnl * 0.60) + (win_rate * 100.0 * 0.25) + (average_pnl * 0.15)) * confidence

        return {
            field: key,
            "trade_count": trade_count,
            "realized_pnl": realized_pnl,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "average_pnl": average_pnl,
            "score": score,
        }

    @staticmethod
    def _apply_limit(rows: list[dict[str, Any]], limit: int | None) -> list[dict[str, Any]]:
        if limit is None:
            return rows
        if limit <= 0:
            raise ProfitabilityRankingEngineError("Ranking limit must be positive")
        return rows[:limit]
