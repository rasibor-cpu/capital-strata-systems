from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence


PAYLOAD_VERSION = "css.ei001.derivatives.stress.v1"


class DerivativesStressServiceError(ValueError):
    """Raised when derivatives stress evidence is malformed."""


class DerivativesStressService:
    def normalize(
        self,
        scenarios: Sequence[Mapping[str, Any]] | None,
        *,
        source: str = "OPTIONS_INCOME",
        asset_class: str = "OPTIONS",
        status: str = "UNAVAILABLE",
    ) -> dict[str, Any]:
        rows = [dict(row) for row in (scenarios or [])]
        rows.sort(key=lambda row: str(row.get("scenario", row.get("name", ""))))
        max_loss = 0.0
        for row in rows:
            estimate = abs(_number(row.get("estimated_loss", row.get("estimated_stressed_loss", 0.0)), "estimated_loss"))
            max_loss = max(max_loss, estimate)
        return {
            "payload_version": PAYLOAD_VERSION,
            "asset_class": str(asset_class or "DERIVATIVES").upper(),
            "subsystem": str(source or "UNKNOWN").upper(),
            "status": str(status or "UNAVAILABLE").upper(),
            "scenario_count": len(rows),
            "scenarios": rows,
            "max_estimated_loss": round(max_loss, 8),
            "scenario_results": rows,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
            "paper_only": True,
        }

    def options_income_contribution(self, stress_report: Mapping[str, Any]) -> dict[str, Any]:
        report = dict(stress_report)
        scenarios = report.get("scenarios", report.get("scenario_results", []))
        return self.normalize(scenarios, source="OPTIONS_INCOME", asset_class="OPTIONS", status=str(report.get("status", report.get("risk_status", "UNAVAILABLE"))))


def build_options_income_derivatives_stress(stress_report: Mapping[str, Any]) -> dict[str, Any]:
    return DerivativesStressService().options_income_contribution(stress_report)


def _number(value: Any, field: str) -> float:
    try:
        result = float(value or 0.0)
    except (TypeError, ValueError) as exc:
        raise DerivativesStressServiceError(f"invalid numeric value: {field}") from exc
    if not isfinite(result):
        raise DerivativesStressServiceError(f"non-finite numeric value: {field}")
    return result


__all__ = ["DerivativesStressService", "DerivativesStressServiceError", "build_options_income_derivatives_stress"]
