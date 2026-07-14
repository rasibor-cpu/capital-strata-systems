from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from backend.options.paper_position_repository import SAFE_FLAGS


@dataclass(frozen=True)
class DiversificationReport:
    by_underlying: dict[str, float]
    by_expiry: dict[str, float]
    by_strategy: dict[str, float]
    by_sector: dict[str, float]
    assignment_concentration: dict[str, float]
    diversification_score: float
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "by_underlying": self.by_underlying,
            "by_expiry": self.by_expiry,
            "by_strategy": self.by_strategy,
            "by_sector": self.by_sector,
            "assignment_concentration": self.assignment_concentration,
            "diversification_score": self.diversification_score,
            **SAFE_FLAGS,
        }


class OptionsIncomeDiversificationAnalyzer:
    def analyze(self, allocations: Sequence[Mapping[str, Any]], *, sector_by_underlying: Mapping[str, str] | None = None) -> DiversificationReport:
        total = sum(float(row.get("collateral", 0.0) or 0.0) for row in allocations)
        sector_map = {str(key).upper(): str(value).upper() for key, value in dict(sector_by_underlying or {}).items()}
        by_underlying = _distribution(allocations, "underlying", total)
        by_expiry = _distribution(allocations, "expiry", total)
        by_strategy = _distribution(allocations, "strategy", total)
        by_sector: dict[str, float] = {}
        assignment: dict[str, float] = {}
        if total > 0.0:
            for row in allocations:
                underlying = str(row.get("underlying") or "UNKNOWN").strip().upper()
                sector = sector_map.get(underlying, "UNKNOWN")
                by_sector[sector] = by_sector.get(sector, 0.0) + float(row.get("collateral", 0.0) or 0.0)
                assignment[underlying] = assignment.get(underlying, 0.0) + float(row.get("assignment_exposure", 0.0) or 0.0)
            by_sector = {key: round(value / total, 8) for key, value in sorted(by_sector.items())}
            assignment = {key: round(value / total, 8) for key, value in sorted(assignment.items())}
        max_bucket = max([0.0, *by_underlying.values(), *by_expiry.values(), *by_strategy.values(), *by_sector.values(), *assignment.values()])
        score = round(max(0.0, min(100.0, 100.0 - max_bucket * 70.0)), 6)
        return DiversificationReport(
            by_underlying=by_underlying,
            by_expiry=by_expiry,
            by_strategy=by_strategy,
            by_sector=by_sector,
            assignment_concentration=assignment,
            diversification_score=score,
        )


def _distribution(rows: Sequence[Mapping[str, Any]], field: str, total: float) -> dict[str, float]:
    if total <= 0.0:
        return {}
    by_group: dict[str, float] = {}
    for row in rows:
        group = str(row.get(field) or "UNKNOWN").strip().upper()
        by_group[group] = by_group.get(group, 0.0) + float(row.get("collateral", 0.0) or 0.0)
    return {key: round(value / total, 8) for key, value in sorted(by_group.items())}


__all__ = ["DiversificationReport", "OptionsIncomeDiversificationAnalyzer"]
