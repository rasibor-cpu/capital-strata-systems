from datetime import datetime, timezone
from decimal import Decimal

from backend.research import (
    CertificationPolicy,
    ResearchEvidence,
    certify_research_evidence,
)


NOW = datetime(2026, 9, 15, 1, 30, tzinfo=timezone.utc)


def evidence(**overrides):
    values = {
        "research_id": "research-001",
        "strategy_id": "strategy-alpha",
        "dataset_id": "dataset-001",
        "asset_class": "EQUITY",
        "sample_count": 2000,
        "trade_count": 120,
        "total_return_pct": Decimal("0.18"),
        "benchmark_return_pct": Decimal("0.10"),
        "max_drawdown_pct": Decimal("0.12"),
        "sharpe_ratio": Decimal("1.10"),
        "profit_factor": Decimal("1.40"),
        "win_rate": Decimal("0.58"),
        "out_of_sample": True,
        "walk_forward_splits": 5,
        "stress_test_passed": True,
        "data_quality_passed": True,
        "generated_at_utc": NOW,
    }
    values.update(overrides)
    return ResearchEvidence(**values)


def test_strong_evidence_certifies_shadow_only():
    result = certify_research_evidence(evidence())
    assert result.status == "CERTIFIED_SHADOW"
    assert result.approved_for_shadow is True
    assert result.approved_for_live is False
    assert result.human_approval_required is True
    assert result.excess_return_pct == Decimal("0.08")


def test_benchmark_underperformance_requires_review():
    result = certify_research_evidence(
        evidence(total_return_pct=Decimal("0.08"), benchmark_return_pct=Decimal("0.10"))
    )
    assert result.status == "REVIEW_REQUIRED"
    assert "NO_POSITIVE_EXCESS_RETURN" in result.reason_codes


def test_out_of_sample_is_required():
    result = certify_research_evidence(evidence(out_of_sample=False))
    assert "OUT_OF_SAMPLE_REQUIRED" in result.reason_codes
    assert result.approved_for_shadow is False


def test_walk_forward_depth_is_required():
    result = certify_research_evidence(evidence(walk_forward_splits=1))
    assert "INSUFFICIENT_WALK_FORWARD_SPLITS" in result.reason_codes


def test_stress_failure_blocks_certification():
    result = certify_research_evidence(evidence(stress_test_passed=False))
    assert "STRESS_TEST_REQUIRED" in result.reason_codes


def test_data_quality_failure_blocks_certification():
    result = certify_research_evidence(evidence(data_quality_passed=False))
    assert "DATA_QUALITY_REQUIRED" in result.reason_codes


def test_drawdown_limit_blocks_certification():
    result = certify_research_evidence(evidence(max_drawdown_pct=Decimal("0.40")))
    assert "DRAWDOWN_ABOVE_MAXIMUM" in result.reason_codes


def test_insufficient_trade_count_blocks_certification():
    result = certify_research_evidence(evidence(trade_count=5))
    assert "INSUFFICIENT_TRADES" in result.reason_codes


def test_invalid_timestamp_is_rejected():
    result = certify_research_evidence(
        evidence(generated_at_utc=datetime(2026, 9, 15, 1, 30))
    )
    assert result.status == "REJECTED_INVALID_EVIDENCE"
    assert "generated_at_utc:NOT_UTC" in result.reason_codes


def test_invalid_win_rate_is_rejected():
    result = certify_research_evidence(evidence(win_rate=Decimal("1.20")))
    assert result.status == "REJECTED_INVALID_EVIDENCE"
    assert "win_rate:OUT_OF_RANGE" in result.reason_codes


def test_policy_can_be_stricter_without_code_change():
    strict = CertificationPolicy(min_sharpe_ratio=Decimal("1.50"))
    result = certify_research_evidence(evidence(), strict)
    assert result.status == "REVIEW_REQUIRED"
    assert "SHARPE_BELOW_MINIMUM" in result.reason_codes


def test_no_execution_surface_exists():
    result = certify_research_evidence(evidence())
    assert result.approved_for_live is False
    assert not hasattr(result, "place_order")
    assert not hasattr(result, "submit_order")
