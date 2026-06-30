from __future__ import annotations

from typing import Any, Iterable, Mapping


class CapitalRotationEngineError(RuntimeError):
    """Fail-closed exception for capital rotation recommendations."""


class CapitalRotationEngine:
    """
    Deterministic, advisory-only capital rotation recommendation engine.
    """

    def recommend(
        self,
        candidates: Iterable[Mapping[str, Any]] | None,
        portfolio_intelligence: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if candidates is None:
            return self._unavailable("candidate_allocations_unavailable")
        if not isinstance(candidates, Iterable):
            return self._unavailable("candidate_allocations_must_be_iterable")

        rows = []
        for raw in candidates:
            if not isinstance(raw, Mapping):
                return self._unavailable("candidate_row_not_mapping")
            asset_class = str(raw.get("asset_class") or raw.get("name") or "").strip().upper()
            if not asset_class:
                return self._unavailable("candidate_asset_class_missing")
            rows.append(
                {
                    "asset_class": asset_class,
                    "base_weight": max(0.0, self._float(raw.get("current_allocation", raw.get("target_allocation", 0.0)))),
                    "expected_return": self._float(raw.get("expected_return", raw.get("expected_edge", 0.0))),
                    "drawdown": max(0.0, self._float(raw.get("drawdown", raw.get("max_drawdown", 0.0)))),
                    "sortino": self._float(raw.get("sortino", raw.get("sortino_ratio", 0.0))),
                    "capital_efficiency": self._float(raw.get("capital_efficiency", 0.0)),
                    "concentration": max(0.0, self._float(raw.get("concentration", 0.0))),
                    "correlation": max(0.0, self._float(raw.get("correlation", raw.get("correlation_score", 0.0)))),
                }
            )

        if not rows:
            return self._limited_no_candidates()

        defensive_multiplier = 0.85
        if isinstance(portfolio_intelligence, Mapping):
            if str(portfolio_intelligence.get("portfolio_status", "")).upper() == "DEFENSIVE":
                defensive_multiplier = 0.65

        scored = []
        for row in rows:
            penalty = (
                min(0.35, row["drawdown"])
                + max(0.0, 1.0 - row["sortino"]) * 0.10
                + max(0.0, 0.60 - row["capital_efficiency"]) * 0.20
                + max(0.0, row["concentration"] - 0.35) * 0.30
                + max(0.0, row["correlation"] - 0.45) * 0.25
            )
            reward = max(0.0, row["expected_return"]) * 0.20
            base = row["base_weight"] if row["base_weight"] > 0.0 else 1.0
            score = max(0.0, base * (1.0 + reward - penalty) * defensive_multiplier)
            scored.append({"asset_class": row["asset_class"], "score": score, "penalty": penalty})

        allocations = self._allocate_basis_points(scored)
        total = round(sum(allocations.values()), 2)
        if total != 100.0:
            return self._unavailable("allocation_normalization_failed")

        explanations = [
            f"{row['asset_class']}: score={row['score']:.6f}, penalty={row['penalty']:.6f}"
            for row in sorted(scored, key=lambda item: item["asset_class"])
        ]
        return {
            "status": "OK",
            "advisory_only": True,
            "execution_allowed": False,
            "target_allocations": allocations,
            "total_allocation": total,
            "recommendation": "ROTATE_CAPITAL" if len(allocations) > 1 else "MAINTAIN",
            "explainability": explanations,
        }

    @staticmethod
    def _allocate_basis_points(scored: list[dict[str, Any]]) -> dict[str, float]:
        total_score = sum(row["score"] for row in scored)
        if total_score <= 0.0:
            return {"CASH": 100.0}

        basis_rows = []
        allocated = 0
        for row in sorted(scored, key=lambda item: item["asset_class"]):
            exact = (row["score"] / total_score) * 10000.0
            whole = int(exact)
            allocated += whole
            basis_rows.append({"asset_class": row["asset_class"], "basis_points": whole, "remainder": exact - whole})

        remaining = 10000 - allocated
        for row in sorted(basis_rows, key=lambda item: (-item["remainder"], item["asset_class"]))[:remaining]:
            row["basis_points"] += 1

        return {
            row["asset_class"]: round(row["basis_points"] / 100.0, 2)
            for row in sorted(basis_rows, key=lambda item: item["asset_class"])
        }

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _unavailable(message: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "advisory_only": True,
            "execution_allowed": False,
            "target_allocations": {"CASH": 100.0},
            "total_allocation": 100.0,
            "recommendation": "NO_ACTION",
            "explainability": [message],
        }

    @staticmethod
    def _limited_no_candidates() -> dict[str, Any]:
        return {
            "status": "LIMITED",
            "advisory_only": True,
            "execution_allowed": False,
            "candidate_allocations": [],
            "target_allocations": {},
            "total_allocation": 0.0,
            "recommendation": "HOLD_CURRENT",
            "explainability": ["No current exposure."],
        }
