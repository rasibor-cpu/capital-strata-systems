from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .opportunity_proposal import OpportunityProposal


ALLOWED_ASSET_CLASSES = {
    "EQUITY",
    "ETF",
    "FX",
    "CRYPTO",
    "FUTURES",
    "OPTIONS",
}

ALLOWED_SIDES = {"BUY", "SELL"}

REQUIRED_FIELDS = (
    "proposal_id",
    "source",
    "broker",
    "symbol",
    "asset_class",
    "side",
    "probability_win",
    "confidence",
    "capital_required",
    "max_drawdown_pct",
    "expected_return_pct",
    "liquidity_score",
    "regime_alignment",
    "observed_at_utc",
)


@dataclass(frozen=True)
class OpportunityValidationResult:
    valid: bool
    errors: tuple[str, ...]
    proposal: OpportunityProposal | None = None


def _decimal(value: Any, field: str, errors: list[str]) -> Decimal | None:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        errors.append(f"{field}:INVALID_DECIMAL")
        return None
    if not result.is_finite():
        errors.append(f"{field}:NON_FINITE")
        return None
    return result


def _utc(value: Any, errors: list[str]) -> datetime | None:
    if not isinstance(value, datetime):
        errors.append("observed_at_utc:INVALID_DATETIME")
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        errors.append("observed_at_utc:NAIVE_DATETIME")
        return None
    if value.utcoffset() != timezone.utc.utcoffset(value):
        errors.append("observed_at_utc:NOT_UTC")
        return None
    return value


def _mapping(candidate: OpportunityProposal | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(candidate, OpportunityProposal):
        return candidate.__dict__
    if isinstance(candidate, Mapping):
        return candidate
    raise TypeError("candidate must be an OpportunityProposal or mapping")


def validate_opportunity_proposal(
    candidate: OpportunityProposal | Mapping[str, Any],
) -> OpportunityValidationResult:
    """Fail-closed validation for Phase 155A opportunity proposals."""

    values = _mapping(candidate)
    errors: list[str] = []

    missing = [field for field in REQUIRED_FIELDS if field not in values or values[field] is None]
    if missing:
        errors.extend(f"{field}:MISSING" for field in missing)
        return OpportunityValidationResult(False, tuple(errors), None)

    text_values: dict[str, str] = {}
    for field in ("proposal_id", "source", "broker", "symbol", "asset_class", "side"):
        value = values[field]
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field}:INVALID_TEXT")
        else:
            text_values[field] = value.strip()

    asset_class = text_values.get("asset_class", "").upper()
    side = text_values.get("side", "").upper()

    if asset_class and asset_class not in ALLOWED_ASSET_CLASSES:
        errors.append("asset_class:UNSUPPORTED")
    if side and side not in ALLOWED_SIDES:
        errors.append("side:UNSUPPORTED")

    probability_win = _decimal(values["probability_win"], "probability_win", errors)
    confidence = _decimal(values["confidence"], "confidence", errors)
    capital_required = _decimal(values["capital_required"], "capital_required", errors)
    max_drawdown_pct = _decimal(values["max_drawdown_pct"], "max_drawdown_pct", errors)
    expected_return_pct = _decimal(values["expected_return_pct"], "expected_return_pct", errors)
    liquidity_score = _decimal(values["liquidity_score"], "liquidity_score", errors)
    regime_alignment = _decimal(values["regime_alignment"], "regime_alignment", errors)
    observed_at_utc = _utc(values["observed_at_utc"], errors)

    for name, value in (
        ("probability_win", probability_win),
        ("confidence", confidence),
        ("liquidity_score", liquidity_score),
        ("regime_alignment", regime_alignment),
    ):
        if value is not None and not (Decimal("0") <= value <= Decimal("1")):
            errors.append(f"{name}:OUT_OF_RANGE")

    if capital_required is not None and capital_required <= 0:
        errors.append("capital_required:NON_POSITIVE")

    if max_drawdown_pct is not None and not (Decimal("0") <= max_drawdown_pct <= Decimal("1")):
        errors.append("max_drawdown_pct:OUT_OF_RANGE")

    # Phase 155A validates representation only. Scoring/optimization policy
    # intentionally belongs to later phases.
    if expected_return_pct is not None and expected_return_pct < Decimal("-1"):
        errors.append("expected_return_pct:BELOW_FLOOR")

    if errors:
        return OpportunityValidationResult(False, tuple(errors), None)

    proposal = OpportunityProposal(
        proposal_id=text_values["proposal_id"],
        source=text_values["source"],
        broker=text_values["broker"],
        symbol=text_values["symbol"].upper(),
        asset_class=asset_class,
        side=side,
        probability_win=probability_win,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        capital_required=capital_required,  # type: ignore[arg-type]
        max_drawdown_pct=max_drawdown_pct,  # type: ignore[arg-type]
        expected_return_pct=expected_return_pct,  # type: ignore[arg-type]
        liquidity_score=liquidity_score,  # type: ignore[arg-type]
        regime_alignment=regime_alignment,  # type: ignore[arg-type]
        observed_at_utc=observed_at_utc,  # type: ignore[arg-type]
    )
    return OpportunityValidationResult(True, (), proposal)
