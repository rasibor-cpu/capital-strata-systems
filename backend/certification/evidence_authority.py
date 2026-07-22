"""Production-profile evidence authority (AR-045 / Wave 3)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from backend.certification.production_readiness_models import (
    AcceptanceStatus,
    CertificationEvidence,
)

SYNTHETIC_SCHEMES = frozenset({"evidence", "fixture", "synthetic", "mock"})
SYNTHETIC_SOURCE_MARKERS = frozenset(
    {
        "FIXTURE",
        "SYNTHETIC",
        "CLOCK_INJECT",
        "SIMULATED",
        "PHASE181_VERIFIED_FIXTURE",
    }
)


def resolve_certification_profile(explicit: str | None = None) -> str:
    """
    Return ``production`` or ``fixture_lab``.

    Fail-closed default is ``production`` outside pytest unless explicitly overridden.
    """
    if explicit:
        value = str(explicit).strip().lower()
        if value in {"production", "prod"}:
            return "production"
        if value in {"fixture_lab", "fixture", "lab", "test"}:
            return "fixture_lab"
    env = os.getenv("CSS_CERTIFICATION_PROFILE", "").strip().lower()
    if env in {"production", "prod"}:
        return "production"
    if env in {"fixture_lab", "fixture", "lab", "test"}:
        return "fixture_lab"
    if os.getenv("PYTEST_CURRENT_TEST"):
        return "fixture_lab"
    return "production"


def is_synthetic_reference(reference: str | None) -> bool:
    if not reference:
        return True
    text = str(reference).strip()
    if "://" not in text:
        return False
    scheme = urlparse(text).scheme.lower()
    return scheme in SYNTHETIC_SCHEMES


def is_synthetic_source(source: str | None) -> bool:
    marker = str(source or "").strip().upper()
    if not marker:
        return True
    return any(token in marker for token in SYNTHETIC_SOURCE_MARKERS)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except Exception:
        return None


def evidence_rejection_reason(
    row: CertificationEvidence,
    *,
    profile: str,
    now: datetime | None = None,
) -> str | None:
    """Return rejection reason for production profile, else None if acceptable."""
    if profile != "production":
        return None
    if row.status is not AcceptanceStatus.PASS:
        return "status_not_pass"
    if not row.verified:
        return "not_verified"
    if not row.reference:
        return "missing_reference"
    if not row.observed_at:
        return "missing_observed_at"
    if is_synthetic_reference(row.reference):
        return "synthetic_reference_rejected"
    if is_synthetic_source(row.source):
        return "synthetic_source_rejected"
    expires = getattr(row, "expires_at", None)
    if expires:
        exp_dt = _parse_iso(str(expires))
        clock = now or datetime.now(timezone.utc)
        if exp_dt is None:
            return "invalid_expires_at"
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        if exp_dt <= clock:
            return "evidence_expired"
    return None


def production_evidence_accepted(
    row: CertificationEvidence,
    *,
    profile: str | None = None,
) -> bool:
    resolved = resolve_certification_profile(profile)
    if resolved == "fixture_lab":
        return bool(
            row.status is AcceptanceStatus.PASS
            and row.verified
            and row.reference
            and row.observed_at
        )
    return evidence_rejection_reason(row, profile=resolved) is None


def authority_diagnostics(profile: str | None = None) -> dict[str, Any]:
    resolved = resolve_certification_profile(profile)
    return {
        "certification_profile": resolved,
        "synthetic_schemes_rejected": sorted(SYNTHETIC_SCHEMES),
        "fail_closed": resolved == "production",
        "execution_allowed": False,
        "remediation_id": "AR-045",
    }


__all__ = [
    "authority_diagnostics",
    "evidence_rejection_reason",
    "is_synthetic_reference",
    "is_synthetic_source",
    "production_evidence_accepted",
    "resolve_certification_profile",
]
