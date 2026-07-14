from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence


PAYLOAD_VERSION = "css.ei001.derivatives.exposure.v1"


class DerivativesExposureServiceError(ValueError):
    """Raised when derivatives exposure cannot be normalized safely."""


class DerivativesExposureService:
    def aggregate(
        self,
        positions: Sequence[Mapping[str, Any]] | None = None,
        *,
        source: str = "OPTIONS_INCOME",
        asset_class: str = "OPTIONS",
        greeks_summary: Mapping[str, Any] | None = None,
        assignment_summary: Mapping[str, Any] | None = None,
        collateral_summary: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        rows = [dict(row) for row in (positions or [])]
        portfolio = dict(greeks_summary.get("portfolio", greeks_summary) if isinstance(greeks_summary, Mapping) else {})
        assignment = dict(assignment_summary or {})
        collateral = dict(collateral_summary or {})
        result = {
            "payload_version": PAYLOAD_VERSION,
            "asset_class": str(asset_class or "DERIVATIVES").upper(),
            "subsystem": str(source or "UNKNOWN").upper(),
            "position_count": len(rows),
            "portfolio_delta": _number(portfolio.get("delta", portfolio.get("portfolio_delta", 0.0)), "portfolio_delta"),
            "absolute_delta": _number(portfolio.get("absolute_delta_exposure", portfolio.get("absolute_delta", 0.0)), "absolute_delta"),
            "gamma": _number(portfolio.get("gamma", 0.0), "gamma"),
            "theta": _number(portfolio.get("theta", 0.0), "theta"),
            "vega": _number(portfolio.get("vega", 0.0), "vega"),
            "rho": _number(portfolio.get("rho", 0.0), "rho"),
            "expiry_concentration": _mapping(greeks_summary).get("by_expiry", {}),
            "assignment_exposure": assignment,
            "collateral_exposure": collateral,
            "collateral_utilization": _number(
                collateral.get("portfolio_utilization", collateral.get("collateral_utilization", 0.0)),
                "collateral_utilization",
            ),
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
            "paper_only": True,
        }
        return result

    def options_income_contribution(self, risk_assessment: Mapping[str, Any], portfolio: Mapping[str, Any] | None = None) -> dict[str, Any]:
        risk = dict(risk_assessment)
        return self.aggregate(
            risk.get("greeks_summary", {}).get("position_level", []),
            source="OPTIONS_INCOME",
            asset_class="OPTIONS",
            greeks_summary=risk.get("greeks_summary", {}),
            assignment_summary=risk.get("assignment_summary", risk.get("assignment_exposure", {})),
            collateral_summary=_mapping(portfolio).get("capital", {}),
        )


def build_options_income_derivatives_exposure(risk_assessment: Mapping[str, Any], portfolio: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return DerivativesExposureService().options_income_contribution(risk_assessment, portfolio)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _number(value: Any, field: str) -> float:
    try:
        result = float(value or 0.0)
    except (TypeError, ValueError) as exc:
        raise DerivativesExposureServiceError(f"invalid numeric value: {field}") from exc
    if not isfinite(result):
        raise DerivativesExposureServiceError(f"non-finite numeric value: {field}")
    return round(result, 8)


__all__ = ["DerivativesExposureService", "DerivativesExposureServiceError", "build_options_income_derivatives_exposure"]
