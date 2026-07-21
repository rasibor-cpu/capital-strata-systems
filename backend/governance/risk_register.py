"""Immutable enterprise risk register."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Any

from backend.governance.governance_models import EnterpriseRisk, RiskRating

_WEIGHT = {
    RiskRating.LOW: 1,
    RiskRating.MEDIUM: 2,
    RiskRating.HIGH: 3,
    RiskRating.CRITICAL: 4,
}


class EnterpriseRiskRegister:
    def __init__(self, risks: Iterable[EnterpriseRisk] = ()):
        rows = tuple(risks)
        identifiers = [row.risk_id for row in rows]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("DUPLICATE_ENTERPRISE_RISK_ID")
        for row in rows:
            if not all(
                str(value or "").strip()
                for value in (
                    row.risk_id,
                    row.title,
                    row.owner,
                    row.mitigation,
                    row.review_date,
                    row.certification_status,
                )
            ):
                raise ValueError("ENTERPRISE_RISK_REQUIRED_FIELD_MISSING")
            date.fromisoformat(row.review_date)
        self._risks = rows

    def inventory(self) -> list[dict[str, Any]]:
        return [risk.as_dict() for risk in self._risks]

    def summary(self) -> dict[str, Any]:
        rows = self.inventory()
        score = sum(
            _WEIGHT[RiskRating(row["severity"])]
            * _WEIGHT[RiskRating(row["likelihood"])]
            for row in rows
        )
        return {
            "risk_count": len(rows),
            "critical_count": sum(row["severity"] == "CRITICAL" for row in rows),
            "high_count": sum(row["severity"] == "HIGH" for row in rows),
            "unmitigated_count": sum(
                str(row["certification_status"]).upper()
                not in {"MITIGATED", "ACCEPTED", "CLOSED"}
                for row in rows
            ),
            "aggregate_risk_score": score,
            "by_category": {
                category: sum(row["category"] == category for row in rows)
                for category in sorted({row["category"] for row in rows})
            },
            "formal_certification_claimed": False,
            "execution_allowed": False,
        }


__all__ = ["EnterpriseRiskRegister"]
