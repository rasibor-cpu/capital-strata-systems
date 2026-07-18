"""Canonical constants for CSS Institutional Reports Center (Phase 176)."""

from __future__ import annotations

SCHEMA_VERSION = "css.institutional_reports_center.v1"
DEFINITION_SCHEMA = "css.report_definition.v1"
ARCHIVE_SCHEMA = "css.runtime_reports_archive.v1"
AUDIT_SCHEMA = "css.report_audit.v1"

SAFETY_LOCKS = {
    "advisory_only": True,
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
}

DEFAULT_ARCHIVE_RELATIVE = "artifacts/runtime_reports/reports"
DEFAULT_AUDIT_RELATIVE = "artifacts/runtime_reports/report_audit"
# Preserve Phase 174/175 morning brief path (do not migrate)
MORNING_BRIEF_ARCHIVE_RELATIVE = "artifacts/runtime_reports/morning_briefings"

STATUSES = (
    "AVAILABLE",
    "AVAILABLE_WITH_LIMITATIONS",
    "DATA_UNAVAILABLE",
    "DISABLED",
    "COMING_SOON",
    "DEPRECATED",
)

CATEGORIES = (
    "executive_intelligence",
    "trading_transactions",
    "accounts_cash",
    "portfolio_performance",
    "risk_exposure",
    "broker_execution",
    "treasury",
    "compliance_audit",
    "operations_system",
    "distribution_print_audit",
)

EMAIL_POLICY_DISABLED = "EMAIL_DISABLED"
EMAIL_POLICY_EXECUTIVE_BRIEF = "EXECUTIVE_BRIEF_ADMIN_SUPER_ONLY"

LIFECYCLE = ("DRAFT", "VALIDATING", "FINAL", "FAILED", "SUPERSEDED")

SECRET_KEY_TOKENS = (
    "secret",
    "token",
    "private",
    "credential",
    "password",
    "pem",
    "jwt",
    "api_key",
    "apikey",
    "signature",
    "access_key",
    "private_key",
)
