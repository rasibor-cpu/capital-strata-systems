"""Canonical constants for Phase 174 Executive Intelligence Engine."""

from __future__ import annotations

BRIEF_SCHEMA_VERSION = "css.executive_morning_brief.v1"
ARCHIVE_SCHEMA_VERSION = "css.executive_intelligence_archive.v1"
PLATFORM_CONTRACT = "css.executive_intelligence_platform.v1"
BRIEFING_TYPE = "MORNING"
MARKET_SESSION_DEFAULT = "OVERNIGHT_TO_OPEN"

SAFETY_LOCKS = {
    "advisory_only": True,
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
}

FRESHNESS_LABELS = ("FRESH", "AGING", "STALE", "UNAVAILABLE")
LIFECYCLE_STATES = ("DRAFT", "VALIDATING", "FINAL", "FAILED", "SUPERSEDED")
POSTURE_LIGHTS = ("GREEN", "AMBER", "RED", "UNAVAILABLE")

# Map producer freshness vocab (RuntimeArtifactFreshnessManager) → freeze vocab
FRESHNESS_ALIAS = {
    "FRESH": "FRESH",
    "AGING": "AGING",
    "STALE": "STALE",
    "MISSING": "UNAVAILABLE",
    "NO_RECENT_TRADES": "AGING",
    "UNAVAILABLE": "UNAVAILABLE",
    "DATA UNAVAILABLE": "UNAVAILABLE",
    "UNKNOWN": "UNAVAILABLE",
}

KPI_NAMES = (
    "runtime_health",
    "market_readiness",
    "opportunity_density",
    "decision_quality",
    "learning_velocity",
    "capital_efficiency",
    "risk_stability",
    "broker_reliability",
    "strategy_strength",
    "market_confidence",
    "recommendation_quality",
)

PANEL_IDS = (
    "executive_decision",
    "operational_health",
    "market_intelligence",
    "trading_intelligence",
    "learning",
)

# Heartbeat age seconds beyond which runtime is STALE (aligned with MC/171 policy)
HEARTBEAT_STALE_SECONDS = 120.0

DEFAULT_ARCHIVE_RELATIVE = "artifacts/runtime_reports/morning_briefings"

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
