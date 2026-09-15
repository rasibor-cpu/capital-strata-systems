from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal
from typing import Iterable

from .research_evidence import ResearchEvidence


@dataclass(frozen=True)
class CertificationPolicy:
    min_sample_count: int = 500
    min_trade_count: int = 30
    min_sharpe_ratio: Decimal = Decimal("0.50")
    min_profit_factor: Decimal = Decimal("1.10")
    max_drawdown_pct: Decimal = Decimal("0.25")
    min_walk_forward_splits: int = 3
    require_out_of_sample: bool = True
    require_stress_pass: bool = True
    require_data_quality_pass: bool = True


@dataclass(frozen=True)
class CertificationDecision:
    status: str
    reason_codes: tuple[str, ...]
    excess_return_pct: Decimal
    approved_for_shadow: bool
    approved_for_live: bool
    human_approval_required: bool


def _valid_utc(value) -> bool:
    return (
        value.tzinfo is not None
        and value.utcoffset() is not None
        and value.utcoffset() == timezone.utc.utcoffset(value)
    )


def _validate_evidence(e: ResearchEvidence) -> tuple[str, ...]:
    errors: list[str] = []

    for field_name, value in (
        ("research_id", e.research_id),
        ("strategy_id", e.strategy_id),
        ("dataset_id", e.dataset_id),
        ("asset_class", e.asset_class),
    ):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field_name}:INVALID")

    if e.sample_count <= 0:
        errors.append("sample_count:NON_POSITIVE")
    if e.trade_count < 0:
        errors.append("trade_count:NEGATIVE")
    if not (Decimal("0") <= e.win_rate <= Decimal("1")):
        errors.append("win_rate:OUT_OF_RANGE")
    if not (Decimal("0") <= e.max_drawdown_pct <= Decimal("1")):
        errors.append("max_drawdown_pct:OUT_OF_RANGE")
    if e.profit_factor < 0:
        errors.append("profit_factor:NEGATIVE")
    if e.walk_forward_splits < 0:
        errors.append("walk_forward_splits:NEGATIVE")
    if not _valid_utc(e.generated_at_utc):
        errors.append("generated_at_utc:NOT_UTC")

    decimals: Iterable[Decimal] = (
        e.total_return_pct,
        e.benchmark_return_pct,
        e.max_drawdown_pct,
        e.sharpe_ratio,
        e.profit_factor,
        e.win_rate,
    )
    if any(not x.is_finite() for x in decimals):
        errors.append("decimal:NON_FINITE")

    return tuple(errors)


def certify_research_evidence(
    evidence: ResearchEvidence,
    policy: CertificationPolicy | None = None,
) -> CertificationDecision:
    """Fail-closed certification for research evidence.

    Certification can approve evidence for shadow/advisory research use only.
    It never authorizes live trading or broker execution.
    """

    policy = policy or CertificationPolicy()
    validation_errors = _validate_evidence(evidence)
    excess = evidence.total_return_pct - evidence.benchmark_return_pct

    if validation_errors:
        return CertificationDecision(
            status="REJECTED_INVALID_EVIDENCE",
            reason_codes=validation_errors,
            excess_return_pct=excess,
            approved_for_shadow=False,
            approved_for_live=False,
            human_approval_required=True,
        )

    reasons: list[str] = []

    if evidence.sample_count < policy.min_sample_count:
        reasons.append("INSUFFICIENT_SAMPLE")
    if evidence.trade_count < policy.min_trade_count:
        reasons.append("INSUFFICIENT_TRADES")
    if evidence.sharpe_ratio < policy.min_sharpe_ratio:
        reasons.append("SHARPE_BELOW_MINIMUM")
    if evidence.profit_factor < policy.min_profit_factor:
        reasons.append("PROFIT_FACTOR_BELOW_MINIMUM")
    if evidence.max_drawdown_pct > policy.max_drawdown_pct:
        reasons.append("DRAWDOWN_ABOVE_MAXIMUM")
    if policy.require_out_of_sample and not evidence.out_of_sample:
        reasons.append("OUT_OF_SAMPLE_REQUIRED")
    if evidence.walk_forward_splits < policy.min_walk_forward_splits:
        reasons.append("INSUFFICIENT_WALK_FORWARD_SPLITS")
    if policy.require_stress_pass and not evidence.stress_test_passed:
        reasons.append("STRESS_TEST_REQUIRED")
    if policy.require_data_quality_pass and not evidence.data_quality_passed:
        reasons.append("DATA_QUALITY_REQUIRED")
    if excess <= Decimal("0"):
        reasons.append("NO_POSITIVE_EXCESS_RETURN")

    if reasons:
        return CertificationDecision(
            status="REVIEW_REQUIRED",
            reason_codes=tuple(reasons),
            excess_return_pct=excess,
            approved_for_shadow=False,
            approved_for_live=False,
            human_approval_required=True,
        )

    return CertificationDecision(
        status="CERTIFIED_SHADOW",
        reason_codes=(),
        excess_return_pct=excess,
        approved_for_shadow=True,
        approved_for_live=False,
        human_approval_required=True,
    )
