from datetime import datetime, timezone
from decimal import Decimal

from backend.research.data_quality import (
    DataQualityPolicy,
    DatasetQualityEvidence,
    assess_dataset_quality,
)
from backend.research.benchmark_comparison import (
    BenchmarkMetrics,
    BenchmarkPolicy,
    compare_with_benchmark,
)


NOW = datetime(2026, 9, 15, 1, 30, tzinfo=timezone.utc)


def quality(**overrides):
    values = {
        "dataset_id": "ohlcv-001",
        "source": "certified-fixture",
        "row_count": 5000,
        "expected_columns": ("timestamp", "open", "high", "low", "close", "volume"),
        "present_columns": ("timestamp", "open", "high", "low", "close", "volume"),
        "missing_value_count": 0,
        "duplicate_timestamp_count": 0,
        "monotonic_timestamp_order": True,
        "timezone_aware_utc": True,
        "first_observed_at_utc": datetime(2026, 9, 1, tzinfo=timezone.utc),
        "last_observed_at_utc": NOW,
        "freshness_seconds": 60,
        "checksum_sha256": "a" * 64,
    }
    values.update(overrides)
    return DatasetQualityEvidence(**values)


def test_clean_dataset_passes():
    result = assess_dataset_quality(quality())
    assert result.status == "PASS"
    assert result.quality_score == 100
    assert result.approved_for_research is True


def test_missing_column_fails_closed():
    result = assess_dataset_quality(
        quality(present_columns=("timestamp", "open", "high", "low", "close"))
    )
    assert result.status == "FAIL"
    assert result.missing_columns == ("volume",)
    assert "REQUIRED_COLUMNS_MISSING" in result.reason_codes


def test_duplicate_timestamps_fail_closed():
    result = assess_dataset_quality(quality(duplicate_timestamp_count=1))
    assert "DUPLICATE_TIMESTAMPS_EXCEED_LIMIT" in result.reason_codes


def test_stale_dataset_fails_closed():
    result = assess_dataset_quality(quality(freshness_seconds=100000))
    assert "DATASET_STALE" in result.reason_codes


def test_bad_checksum_fails_closed():
    result = assess_dataset_quality(quality(checksum_sha256="not-a-hash"))
    assert "INVALID_SHA256" in result.reason_codes


def test_policy_can_allow_bounded_missing_values():
    policy = DataQualityPolicy(max_missing_values=2)
    result = assess_dataset_quality(quality(missing_value_count=2), policy)
    assert result.status == "PASS"


def test_strategy_outperforming_benchmark_passes():
    strategy = BenchmarkMetrics(Decimal("0.20"), Decimal("0.10"), Decimal("1.20"))
    benchmark = BenchmarkMetrics(Decimal("0.12"), Decimal("0.11"), Decimal("0.80"))
    result = compare_with_benchmark(strategy, benchmark)
    assert result.status == "OUTPERFORM"
    assert result.excess_return_pct == Decimal("0.08")
    assert result.approved_for_research is True


def test_strategy_underperforming_return_requires_review():
    strategy = BenchmarkMetrics(Decimal("0.08"), Decimal("0.10"), Decimal("1.20"))
    benchmark = BenchmarkMetrics(Decimal("0.12"), Decimal("0.11"), Decimal("0.80"))
    result = compare_with_benchmark(strategy, benchmark)
    assert result.status == "REVIEW_REQUIRED"
    assert "EXCESS_RETURN_NOT_ABOVE_MINIMUM" in result.reason_codes


def test_sharpe_disadvantage_requires_review():
    strategy = BenchmarkMetrics(Decimal("0.20"), Decimal("0.10"), Decimal("0.60"))
    benchmark = BenchmarkMetrics(Decimal("0.12"), Decimal("0.11"), Decimal("0.80"))
    result = compare_with_benchmark(strategy, benchmark)
    assert "SHARPE_SPREAD_BELOW_MINIMUM" in result.reason_codes


def test_material_drawdown_disadvantage_requires_review():
    strategy = BenchmarkMetrics(Decimal("0.20"), Decimal("0.20"), Decimal("1.20"))
    benchmark = BenchmarkMetrics(Decimal("0.12"), Decimal("0.10"), Decimal("0.80"))
    result = compare_with_benchmark(strategy, benchmark)
    assert "DRAWDOWN_DISADVANTAGE_TOO_HIGH" in result.reason_codes


def test_nonfinite_benchmark_is_invalid():
    strategy = BenchmarkMetrics(Decimal("0.20"), Decimal("0.10"), Decimal("1.20"))
    benchmark = BenchmarkMetrics(Decimal("NaN"), Decimal("0.10"), Decimal("0.80"))
    result = compare_with_benchmark(strategy, benchmark)
    assert result.status == "INVALID"
    assert result.approved_for_research is False


def test_benchmark_policy_is_configurable():
    policy = BenchmarkPolicy(min_excess_return_pct=Decimal("0.10"))
    strategy = BenchmarkMetrics(Decimal("0.20"), Decimal("0.10"), Decimal("1.20"))
    benchmark = BenchmarkMetrics(Decimal("0.12"), Decimal("0.11"), Decimal("0.80"))
    result = compare_with_benchmark(strategy, benchmark, policy)
    assert "EXCESS_RETURN_NOT_ABOVE_MINIMUM" in result.reason_codes
