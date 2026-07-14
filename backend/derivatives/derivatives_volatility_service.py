from __future__ import annotations

from math import isfinite
from typing import Any, Mapping


PAYLOAD_VERSION = "css.ei001.derivatives.volatility.v1"


class DerivativesVolatilityServiceError(ValueError):
    """Raised when derivatives volatility evidence is malformed."""


class DerivativesVolatilityService:
    def normalize(
        self,
        volatility: Mapping[str, Any] | None,
        *,
        source: str = "OPTIONS_INCOME",
        asset_class: str = "OPTIONS",
    ) -> dict[str, Any]:
        payload = dict(volatility or {})
        exposures = payload.get("vega_by_underlying", payload.get("volatility_by_underlying", {}))
        exposure_total = _number(payload.get("vega_exposure", payload.get("total_vega", 0.0)), "vega_exposure")
        return {
            "payload_version": PAYLOAD_VERSION,
            "asset_class": str(asset_class or "DERIVATIVES").upper(),
            "subsystem": str(source or "UNKNOWN").upper(),
            "status": str(payload.get("status", "UNAVAILABLE")).upper(),
            "volatility_regime": str(payload.get("volatility_regime", "UNKNOWN")),
            "iv_availability": str(payload.get("iv_availability", "UNKNOWN")),
            "vega_exposure": exposure_total,
            "volatility_exposure": payload,
            "by_underlying": dict(exposures) if isinstance(exposures, Mapping) else {},
            "warnings": list(payload.get("warnings", [])) if isinstance(payload.get("warnings", []), list) else [],
            "unavailable_data": list(payload.get("unavailable", payload.get("unavailable_data", []))) if isinstance(payload.get("unavailable", payload.get("unavailable_data", [])), list) else [],
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
            "paper_only": True,
        }

    def options_income_contribution(self, risk_assessment: Mapping[str, Any]) -> dict[str, Any]:
        risk = dict(risk_assessment)
        return self.normalize(risk.get("volatility_summary", risk.get("volatility_risk", {})), source="OPTIONS_INCOME", asset_class="OPTIONS")


def build_options_income_derivatives_volatility(risk_assessment: Mapping[str, Any]) -> dict[str, Any]:
    return DerivativesVolatilityService().options_income_contribution(risk_assessment)


def _number(value: Any, field: str) -> float:
    try:
        result = float(value or 0.0)
    except (TypeError, ValueError) as exc:
        raise DerivativesVolatilityServiceError(f"invalid numeric value: {field}") from exc
    if not isfinite(result):
        raise DerivativesVolatilityServiceError(f"non-finite numeric value: {field}")
    return round(result, 8)


__all__ = ["DerivativesVolatilityService", "DerivativesVolatilityServiceError", "build_options_income_derivatives_volatility"]
