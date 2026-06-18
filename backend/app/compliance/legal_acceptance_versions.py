"""Canonical legal and trading-risk acceptance versions for Phase 1."""

from __future__ import annotations

LEGAL_TERMS = "LEGAL_TERMS"
TRADING_RISK_DISCLOSURE = "TRADING_RISK_DISCLOSURE"

LEGAL_TERMS_CURRENT_VERSION = "phase1.legal_terms.v1"
TRADING_RISK_DISCLOSURE_CURRENT_VERSION = (
    "phase1.trading_risk_disclosure.v1"
)

CURRENT_ACCEPTANCE_VERSIONS = {
    LEGAL_TERMS: LEGAL_TERMS_CURRENT_VERSION,
    TRADING_RISK_DISCLOSURE: (
        TRADING_RISK_DISCLOSURE_CURRENT_VERSION
    ),
}

REQUIRED_ACCEPTANCE_TYPES = (
    LEGAL_TERMS,
    TRADING_RISK_DISCLOSURE,
)


def is_supported_acceptance_type(acceptance_type: str) -> bool:
    return acceptance_type in CURRENT_ACCEPTANCE_VERSIONS


def current_version_for(acceptance_type: str) -> str:
    if not is_supported_acceptance_type(acceptance_type):
        raise ValueError(
            f"Unsupported acceptance type: {acceptance_type}"
        )

    return CURRENT_ACCEPTANCE_VERSIONS[acceptance_type]