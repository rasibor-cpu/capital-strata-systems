from __future__ import annotations

from typing import Any


class CapitalAllocationEngineError(RuntimeError):
    """Explicit fail-closed exception for capital allocation failures."""


class CapitalAllocationEngine:
    """Convert profitability rankings into backend-only capital allocation recommendations."""

    def allocate(
        self,
        ranking: list[dict[str, Any]],
        *,
        available_capital: float,
        max_symbol_weight: float,
        min_trade_count: int,
        restricted_score_threshold: float,
    ) -> list[dict[str, Any]]:
        self._validate_inputs(
            available_capital=available_capital,
            max_symbol_weight=max_symbol_weight,
            min_trade_count=min_trade_count,
            restricted_score_threshold=restricted_score_threshold,
        )

        if not ranking:
            return []

        normalized_rows: list[dict[str, Any]] = []
        for row in ranking:
            symbol = str(row.get("symbol", "")).strip()
            if not symbol:
                raise CapitalAllocationEngineError("Ranking contains a symbol without a name")
            trade_count = int(row.get("trade_count", 0))
            score = float(row.get("score", 0.0))
            realized_pnl = float(row.get("realized_pnl", 0.0))
            normalized_rows.append(
                {
                    "symbol": symbol,
                    "score": score,
                    "trade_count": trade_count,
                    "realized_pnl": realized_pnl,
                }
            )

        weights = [0.0] * len(normalized_rows)
        preferred_candidates = [
            (index, row)
            for index, row in enumerate(normalized_rows)
            if row["trade_count"] >= min_trade_count and row["score"] > restricted_score_threshold
        ]
        preferred_candidates.sort(
            key=lambda item: (
                -float(item[1]["score"]),
                -float(item[1]["realized_pnl"]),
                str(item[1]["symbol"]),
            ),
        )

        remaining_weight = 1.0
        remaining_score_total = sum(float(row["score"]) for _, row in preferred_candidates)
        for index, row in preferred_candidates:
            if remaining_weight <= 1e-12 or remaining_score_total <= 1e-12:
                break
            score = float(row["score"])
            raw_weight = remaining_weight * (score / remaining_score_total)
            weight = min(max_symbol_weight, raw_weight)
            weight = min(weight, remaining_weight)
            weights[index] = weight
            remaining_weight -= weight
            remaining_score_total -= score

        allocations: list[dict[str, Any]] = []
        for row in normalized_rows:
            index = normalized_rows.index(row)
            trade_count = int(row["trade_count"])
            score = float(row["score"])
            weight = weights[index]
            if trade_count < min_trade_count:
                status = "RESTRICTED"
                weight = 0.0
            elif score <= restricted_score_threshold:
                status = "NEUTRAL"
                weight = 0.0
            else:
                status = "PREFERRED"

            allocations.append(
                {
                    "symbol": row["symbol"],
                    "score": score,
                    "trade_count": trade_count,
                    "realized_pnl": float(row["realized_pnl"]),
                    "allocation_weight": weight,
                    "allocation_amount": available_capital * weight,
                    "status": status,
                }
            )

        if sum(row["allocation_weight"] for row in allocations) > 1.0 + 1e-9:
            raise CapitalAllocationEngineError("Total allocation weight exceeds 1.0")

        return allocations

    @staticmethod
    def _validate_inputs(
        *,
        available_capital: float,
        max_symbol_weight: float,
        min_trade_count: int,
        restricted_score_threshold: float,
    ) -> None:
        try:
            available_capital = float(available_capital)
            max_symbol_weight = float(max_symbol_weight)
            restricted_score_threshold = float(restricted_score_threshold)
            min_trade_count = int(min_trade_count)
        except (TypeError, ValueError) as exc:
            raise CapitalAllocationEngineError("Capital allocation inputs must be numeric") from exc

        if available_capital <= 0.0:
            raise CapitalAllocationEngineError("available_capital must be positive")
        if not 0.0 < max_symbol_weight <= 1.0:
            raise CapitalAllocationEngineError("max_symbol_weight must be between 0 and 1")
        if min_trade_count <= 0:
            raise CapitalAllocationEngineError("min_trade_count must be positive")
        if restricted_score_threshold < 0.0:
            raise CapitalAllocationEngineError("restricted_score_threshold must be non-negative")
