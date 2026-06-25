from __future__ import annotations

from typing import Any, Mapping


class OpportunityRankingEngineError(RuntimeError):
    """Fail-closed exception for opportunity ranking operations."""


class OpportunityRankingEngine:
    """Deterministically ranks scored trade opportunities."""

    def rank(
        self,
        candidates: list[Mapping[str, Any]],
        *,
        top_n: int | None = None,
        minimum_quality_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        if not isinstance(candidates, list):
            raise OpportunityRankingEngineError("candidates must be a list")
        try:
            minimum_score = float(minimum_quality_score)
        except (TypeError, ValueError) as exc:
            raise OpportunityRankingEngineError("minimum_quality_score must be numeric") from exc

        if top_n is not None and int(top_n) <= 0:
            raise OpportunityRankingEngineError("top_n must be positive when provided")

        normalized: list[dict[str, Any]] = []
        for candidate in candidates:
            normalized.append(self._normalize_candidate(candidate))

        filtered = [candidate for candidate in normalized if candidate["quality_score"] >= minimum_score]
        ranked = sorted(
            filtered,
            key=lambda row: (
                -row["quality_score"],
                -row["confidence"],
                row["symbol"],
                row["trade_id"],
            ),
        )

        if top_n is None:
            return ranked
        return ranked[: int(top_n)]

    @staticmethod
    def _normalize_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(candidate, Mapping):
            raise OpportunityRankingEngineError("candidate must be a mapping")

        trade_id = str(candidate.get("trade_id") or "").strip()
        symbol = str(candidate.get("symbol") or "").strip().upper()
        if not trade_id:
            raise OpportunityRankingEngineError("candidate trade_id must be non-empty")
        if not symbol:
            raise OpportunityRankingEngineError("candidate symbol must be non-empty")

        try:
            quality_score = float(candidate.get("quality_score"))
            confidence = float(candidate.get("confidence"))
        except (TypeError, ValueError) as exc:
            raise OpportunityRankingEngineError("candidate quality_score/confidence must be numeric") from exc

        return {
            **dict(candidate),
            "trade_id": trade_id,
            "symbol": symbol,
            "quality_score": quality_score,
            "confidence": confidence,
        }
