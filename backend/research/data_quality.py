from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class DatasetQualityEvidence:
    dataset_id: str
    source: str
    row_count: int
    expected_columns: tuple[str, ...]
    present_columns: tuple[str, ...]
    missing_value_count: int
    duplicate_timestamp_count: int
    monotonic_timestamp_order: bool
    timezone_aware_utc: bool
    first_observed_at_utc: datetime
    last_observed_at_utc: datetime
    freshness_seconds: int
    checksum_sha256: str


@dataclass(frozen=True)
class DataQualityDecision:
    status: str
    reason_codes: tuple[str, ...]
    missing_columns: tuple[str, ...]
    quality_score: int
    approved_for_research: bool


@dataclass(frozen=True)
class DataQualityPolicy:
    min_rows: int = 100
    max_missing_values: int = 0
    max_duplicate_timestamps: int = 0
    max_freshness_seconds: int = 86_400


def _is_utc(value: datetime) -> bool:
    return (
        value.tzinfo is not None
        and value.utcoffset() is not None
        and value.utcoffset() == timezone.utc.utcoffset(value)
    )


def assess_dataset_quality(
    evidence: DatasetQualityEvidence,
    policy: DataQualityPolicy | None = None,
) -> DataQualityDecision:
    policy = policy or DataQualityPolicy()
    reasons: list[str] = []

    if not evidence.dataset_id.strip():
        reasons.append("DATASET_ID_MISSING")
    if not evidence.source.strip():
        reasons.append("SOURCE_MISSING")
    if evidence.row_count < policy.min_rows:
        reasons.append("INSUFFICIENT_ROWS")
    if evidence.missing_value_count < 0:
        reasons.append("NEGATIVE_MISSING_COUNT")
    elif evidence.missing_value_count > policy.max_missing_values:
        reasons.append("MISSING_VALUES_EXCEED_LIMIT")
    if evidence.duplicate_timestamp_count < 0:
        reasons.append("NEGATIVE_DUPLICATE_COUNT")
    elif evidence.duplicate_timestamp_count > policy.max_duplicate_timestamps:
        reasons.append("DUPLICATE_TIMESTAMPS_EXCEED_LIMIT")
    if not evidence.monotonic_timestamp_order:
        reasons.append("TIMESTAMPS_NOT_MONOTONIC")
    if not evidence.timezone_aware_utc:
        reasons.append("TIMESTAMPS_NOT_DECLARED_UTC")
    if not _is_utc(evidence.first_observed_at_utc) or not _is_utc(evidence.last_observed_at_utc):
        reasons.append("OBSERVATION_BOUNDS_NOT_UTC")
    elif evidence.last_observed_at_utc < evidence.first_observed_at_utc:
        reasons.append("OBSERVATION_BOUNDS_REVERSED")
    if evidence.freshness_seconds < 0:
        reasons.append("NEGATIVE_FRESHNESS")
    elif evidence.freshness_seconds > policy.max_freshness_seconds:
        reasons.append("DATASET_STALE")
    if not _SHA256_RE.fullmatch(evidence.checksum_sha256):
        reasons.append("INVALID_SHA256")

    expected = tuple(dict.fromkeys(c.strip() for c in evidence.expected_columns if c.strip()))
    present = {c.strip() for c in evidence.present_columns if c.strip()}
    missing_columns = tuple(c for c in expected if c not in present)
    if missing_columns:
        reasons.append("REQUIRED_COLUMNS_MISSING")

    # Deterministic 0-100 evidence-quality score. Each failed independent
    # dimension removes a bounded amount; status is still fail-closed.
    dimensions = (
        evidence.row_count >= policy.min_rows,
        evidence.missing_value_count >= 0 and evidence.missing_value_count <= policy.max_missing_values,
        evidence.duplicate_timestamp_count >= 0 and evidence.duplicate_timestamp_count <= policy.max_duplicate_timestamps,
        evidence.monotonic_timestamp_order,
        evidence.timezone_aware_utc and _is_utc(evidence.first_observed_at_utc) and _is_utc(evidence.last_observed_at_utc),
        evidence.freshness_seconds >= 0 and evidence.freshness_seconds <= policy.max_freshness_seconds,
        not missing_columns,
        bool(_SHA256_RE.fullmatch(evidence.checksum_sha256)),
        bool(evidence.dataset_id.strip()),
        bool(evidence.source.strip()),
    )
    quality_score = sum(10 for ok in dimensions if ok)

    passed = not reasons
    return DataQualityDecision(
        status="PASS" if passed else "FAIL",
        reason_codes=tuple(reasons),
        missing_columns=missing_columns,
        quality_score=quality_score,
        approved_for_research=passed,
    )
