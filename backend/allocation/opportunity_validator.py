from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from .opportunity_proposal import ALLOWED_ASSET_CLASSES, OpportunityProposal


_REQUIRED_FIELDS: tuple[str, ...] = (
    "proposal_id",
    "symbol",
    "asset_class",
    "probability",
    "confidence",
    "expected_drawdown_pct",
    "risk_score",
    "requested_capital",
)


class OpportunityProposalValidator:
    """Fail-closed validator for CAIE opportunity proposal payloads."""

    def validate(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        errors: list[dict[str, str]] = []

        if not isinstance(payload, Mapping):
            errors.append(
                {
                    "field": "proposal",
                    "code": "INVALID_PAYLOAD_TYPE",
                    "reason": "proposal_payload_must_be_mapping",
                }
            )
            return {"valid": False, "errors": errors, "normalized": None}

        for field in _REQUIRED_FIELDS:
            if field not in payload or self._is_blank(payload.get(field)):
                errors.append(
                    {
                        "field": field,
                        "code": "MISSING_REQUIRED_FIELD",
                        "reason": f"missing_required_field:{field}",
                    }
                )

        if errors:
            return {"valid": False, "errors": errors, "normalized": None}

        self._validate_asset_class(payload, errors)
        self._validate_probability(payload, errors)
        self._validate_confidence(payload, errors)
        self._validate_drawdown(payload, errors)
        self._validate_risk_score(payload, errors)
        self._validate_requested_capital(payload, errors)

        if errors:
            return {"valid": False, "errors": errors, "normalized": None}

        proposal = OpportunityProposal.from_payload(payload)
        return {
            "valid": True,
            "errors": [],
            "normalized": asdict(proposal),
        }

    @staticmethod
    def _is_blank(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _append_type_error(errors: list[dict[str, str]], field: str) -> None:
        errors.append(
            {
                "field": field,
                "code": "INVALID_NUMERIC_TYPE",
                "reason": f"invalid_numeric_type:{field}",
            }
        )

    def _validate_asset_class(self, payload: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
        asset_class = str(payload.get("asset_class", "")).strip().upper()
        if asset_class not in ALLOWED_ASSET_CLASSES:
            errors.append(
                {
                    "field": "asset_class",
                    "code": "INVALID_ASSET_CLASS",
                    "reason": "invalid_asset_class",
                }
            )

    def _validate_probability(self, payload: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
        try:
            probability = float(payload["probability"])
        except (TypeError, ValueError):
            self._append_type_error(errors, "probability")
            return
        if probability < 0.0 or probability > 1.0:
            errors.append(
                {
                    "field": "probability",
                    "code": "OUT_OF_RANGE",
                    "reason": "probability_must_be_between_0_and_1",
                }
            )

    def _validate_confidence(self, payload: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
        try:
            confidence = float(payload["confidence"])
        except (TypeError, ValueError):
            self._append_type_error(errors, "confidence")
            return
        if confidence < 0.0 or confidence > 1.0:
            errors.append(
                {
                    "field": "confidence",
                    "code": "OUT_OF_RANGE",
                    "reason": "confidence_must_be_between_0_and_1",
                }
            )

    def _validate_drawdown(self, payload: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
        try:
            drawdown = float(payload["expected_drawdown_pct"])
        except (TypeError, ValueError):
            self._append_type_error(errors, "expected_drawdown_pct")
            return
        if drawdown < 0.0 or drawdown > 1.0:
            errors.append(
                {
                    "field": "expected_drawdown_pct",
                    "code": "OUT_OF_RANGE",
                    "reason": "expected_drawdown_pct_must_be_between_0_and_1",
                }
            )

    def _validate_risk_score(self, payload: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
        try:
            risk_score = float(payload["risk_score"])
        except (TypeError, ValueError):
            self._append_type_error(errors, "risk_score")
            return
        if risk_score < 0.0 or risk_score > 100.0:
            errors.append(
                {
                    "field": "risk_score",
                    "code": "OUT_OF_RANGE",
                    "reason": "risk_score_must_be_between_0_and_100",
                }
            )

    def _validate_requested_capital(self, payload: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
        try:
            requested_capital = float(payload["requested_capital"])
        except (TypeError, ValueError):
            self._append_type_error(errors, "requested_capital")
            return
        if requested_capital <= 0.0:
            errors.append(
                {
                    "field": "requested_capital",
                    "code": "NON_POSITIVE_CAPITAL",
                    "reason": "requested_capital_must_be_positive",
                }
            )


def validate_opportunity_proposal(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return OpportunityProposalValidator().validate(payload)
