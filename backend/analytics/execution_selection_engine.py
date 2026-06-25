from __future__ import annotations

from typing import Any, Mapping


class ExecutionSelectionEngineError(RuntimeError):
    """Fail-closed exception for execution selection."""


class ExecutionSelectionEngine:
    """Selects eligible ranked opportunities without triggering execution side effects."""

    def select(
        self,
        ranked_candidates: list[Mapping[str, Any]],
        *,
        acceptance_threshold: float,
        top_n: int,
    ) -> dict[str, Any]:
        if not isinstance(ranked_candidates, list):
            raise ExecutionSelectionEngineError("ranked_candidates must be a list")
        try:
            threshold = float(acceptance_threshold)
        except (TypeError, ValueError) as exc:
            raise ExecutionSelectionEngineError("acceptance_threshold must be numeric") from exc
        if threshold < 0.0 or threshold > 100.0:
            raise ExecutionSelectionEngineError("acceptance_threshold must be between 0 and 100")
        if int(top_n) <= 0:
            raise ExecutionSelectionEngineError("top_n must be positive")

        if not ranked_candidates:
            return {
                "selected": [],
                "rejected": [],
                "selection_summary": {
                    "accepted_count": 0,
                    "rejected_count": 0,
                    "acceptance_threshold": threshold,
                },
            }

        normalized = [self._normalize_candidate(row) for row in ranked_candidates]
        ordered = sorted(
            normalized,
            key=lambda row: (-row["quality_score"], -row["confidence"], row["symbol"], row["trade_id"]),
        )

        selected: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for row in ordered:
            reason = ""
            if row["recommendation"] == "REJECT":
                reason = "recommendation_reject"
            elif row["quality_score"] < threshold:
                reason = "below_threshold"
            elif len(selected) >= int(top_n):
                reason = "outside_top_n"

            if reason:
                rejected.append(
                    {
                        "trade_id": row["trade_id"],
                        "symbol": row["symbol"],
                        "reason": reason,
                        "quality_score": row["quality_score"],
                    }
                )
                continue

            selected.append({**row, "selection_reason": "eligible_top_ranked"})

        return {
            "selected": selected,
            "rejected": rejected,
            "selection_summary": {
                "accepted_count": len(selected),
                "rejected_count": len(rejected),
                "acceptance_threshold": threshold,
            },
        }

    @staticmethod
    def _normalize_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(candidate, Mapping):
            raise ExecutionSelectionEngineError("candidate must be a mapping")
        trade_id = str(candidate.get("trade_id") or "").strip()
        symbol = str(candidate.get("symbol") or "").strip().upper()
        recommendation = str(candidate.get("recommendation") or "").strip().upper()
        if not trade_id:
            raise ExecutionSelectionEngineError("candidate trade_id must be non-empty")
        if not symbol:
            raise ExecutionSelectionEngineError("candidate symbol must be non-empty")
        if not recommendation:
            raise ExecutionSelectionEngineError("candidate recommendation must be non-empty")
        try:
            quality_score = float(candidate.get("quality_score"))
            confidence = float(candidate.get("confidence"))
        except (TypeError, ValueError) as exc:
            raise ExecutionSelectionEngineError("candidate quality_score/confidence must be numeric") from exc

        return {
            **dict(candidate),
            "trade_id": trade_id,
            "symbol": symbol,
            "recommendation": recommendation,
            "quality_score": quality_score,
            "confidence": confidence,
        }
