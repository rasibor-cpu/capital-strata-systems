from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MissionControlSection:
    key: str
    label: str
    route: str
    description: str
    icon: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


MISSION_CONTROL_SECTIONS: tuple[MissionControlSection, ...] = (
    MissionControlSection("executive_overview", "Executive Overview", "/mission-control/executive-overview", "Enterprise status, readiness, capital, alerts, and runtime heartbeat.", "grid"),
    MissionControlSection("reports_center", "Reports", "/mission-control/reports", "Institutional Reports Center — catalogue, generate, library, print, export, and audit.", "file"),
    MissionControlSection("runtime_operations", "Runtime Operations", "/mission-control/runtime-operations", "Runtime cycle, supervisor, subsystem, dependency, API, dashboard, and mobile health.", "activity"),
    MissionControlSection("trade_operations", "Trade Operations", "/mission-control/trade-operations", "Read-only trade decisions, gates, paper positions, orders, fills, rejections, and execution quality.", "route"),
    MissionControlSection("portfolio", "Portfolio", "/mission-control/portfolio", "Equity, cash, exposure, allocation, PnL, drawdown, and performance attribution.", "briefcase"),
    MissionControlSection("market_intelligence", "Market Intelligence", "/mission-control/market-intelligence", "Regime, trend, volatility, liquidity, rankings, watchlists, and data freshness.", "waves"),
    MissionControlSection("risk_command", "Risk Command", "/mission-control/risk-command", "Risk state, limits, breaches, stress, Greeks, margin, kill switch, and governance gates.", "shield"),
    MissionControlSection("options_income", "Options Income", "/mission-control/options-income", "Options Income Engine opportunities, premium, collateral, rolling, Greeks, assignment, and certification.", "layers"),
    MissionControlSection("broker_management", "Broker Management", "/mission-control/broker-management", "Active broker, broker list, selection preview, onboarding shell, capabilities, and safety gates.", "plug"),
    MissionControlSection("alerts_incidents", "Alerts and Incidents", "/mission-control/alerts-incidents", "Active alerts, incident timeline, runtime failures, broker failures, and stale data alerts.", "bell"),
    MissionControlSection("certification_readiness", "Certification and Readiness", "/mission-control/certification-readiness", "RC1, operational, Options Income, broker, runtime, live-disable proof, and blockers.", "badge"),
    MissionControlSection("audit_explainability", "Audit and Explainability", "/mission-control/audit-explainability", "Decision explanations, evidence, correlation IDs, audit events, warnings, and failures.", "search"),
    MissionControlSection("learning_performance", "Learning and Performance", "/mission-control/learning-performance", "Strategy rankings, attribution, reliability, expectancy, profit factor, and recommendations.", "chart"),
    MissionControlSection("users_governance", "Users and Governance", "/mission-control/users-governance", "Current user, role, unit, session, permissions, RBAC, and governance state.", "users"),
    MissionControlSection("system_configuration", "System Configuration", "/mission-control/system-configuration", "Safe non-secret runtime configuration, limits, flags, endpoints, and refresh settings.", "sliders"),
    MissionControlSection("documentation_runbooks", "Documentation / Runbooks", "/mission-control/documentation-runbooks", "Safe index of architecture, governance, release, certification, and operator runbook documents.", "book"),
)

CREDENTIAL_GOVERNANCE_SECTION = MissionControlSection(
    "credential_governance",
    "Credential Governance",
    "/mission-control/credential-governance",
    "ESMS-001 vault health, ESMS-002 dependencies, rotation, audit, and compliance metadata.",
    "key",
)
ENTERPRISE_IDENTITY_SECTION = MissionControlSection(
    "enterprise_identity",
    "Enterprise Identity & Secrets",
    "/mission-control/enterprise-identity",
    "Canonical identity, secret, vault, rotation, risk, authentication, and audit metadata.",
    "shield-key",
)
ENTERPRISE_OAUTH_SECTION = MissionControlSection(
    "enterprise_oauth",
    "Enterprise OAuth",
    "/mission-control/enterprise-oauth",
    "Provider registration, scopes, lifecycle, expiry, rotation, risk, policy, and audit metadata.",
    "oauth",
)
ENTERPRISE_GOVERNANCE_SECTION = MissionControlSection(
    "enterprise_governance",
    "Executive Governance",
    "/mission-control/enterprise-governance",
    "ISO readiness, continuity, enterprise risk, compliance, and certification blockers.",
    "governance",
)
PRODUCTION_READINESS_SECTION = MissionControlSection(
    "production_readiness",
    "Production Readiness",
    "/mission-control/production-readiness",
    "Operational acceptance, endurance, recovery, deployment, and final certification evidence.",
    "readiness",
)
GOVERNANCE_AUXILIARY_SECTIONS = (
    CREDENTIAL_GOVERNANCE_SECTION,
    ENTERPRISE_IDENTITY_SECTION,
    ENTERPRISE_OAUTH_SECTION,
    ENTERPRISE_GOVERNANCE_SECTION,
    PRODUCTION_READINESS_SECTION,
)

SECTION_BY_KEY = {
    section.key: section
    for section in (*MISSION_CONTROL_SECTIONS, *GOVERNANCE_AUXILIARY_SECTIONS)
}

# URL path segment → section (derived from published routes; no silent EO default).
SECTION_BY_SLUG: dict[str, MissionControlSection] = {}
for _section in (*MISSION_CONTROL_SECTIONS, *GOVERNANCE_AUXILIARY_SECTIONS):
    _route_slug = _section.route.rstrip("/").rsplit("/", 1)[-1].lower()
    SECTION_BY_SLUG[_route_slug] = _section
    SECTION_BY_SLUG[_section.key.replace("_", "-")] = _section
    SECTION_BY_SLUG[_section.key] = _section
# Explicit aliases for clarity / legacy bookmarks
SECTION_BY_SLUG.setdefault("reports", SECTION_BY_KEY["reports_center"])
SECTION_BY_SLUG.setdefault("reports-center", SECTION_BY_KEY["reports_center"])


def resolve_section_slug(section_slug: str | None) -> MissionControlSection | None:
    """Resolve a Mission Control URL slug to a section.

    Returns None for unknown slugs. Never silently falls back to Executive Overview.
    """
    raw = str(section_slug or "").strip().lower()
    if not raw:
        return None
    hyphen = raw.replace("_", "-")
    underscore = raw.replace("-", "_")
    return (
        SECTION_BY_SLUG.get(raw)
        or SECTION_BY_SLUG.get(hyphen)
        or SECTION_BY_SLUG.get(underscore)
        or SECTION_BY_KEY.get(underscore)
    )


def section_for_key(key: str | None) -> MissionControlSection:
    """Resolve a known section key. Unknown keys raise KeyError (fail closed)."""
    normalized = str(key or "").strip().lower().replace("-", "_")
    if normalized == "reports":
        normalized = "reports_center"
    section = SECTION_BY_KEY.get(normalized)
    if section is None:
        raise KeyError(f"unknown_mission_control_section:{normalized or 'EMPTY'}")
    return section


def navigation_payload() -> list[dict[str, str]]:
    return [section.as_dict() for section in MISSION_CONTROL_SECTIONS]


__all__ = [
    "MISSION_CONTROL_SECTIONS",
    "CREDENTIAL_GOVERNANCE_SECTION",
    "ENTERPRISE_IDENTITY_SECTION",
    "ENTERPRISE_OAUTH_SECTION",
    "ENTERPRISE_GOVERNANCE_SECTION",
    "PRODUCTION_READINESS_SECTION",
    "GOVERNANCE_AUXILIARY_SECTIONS",
    "MissionControlSection",
    "SECTION_BY_KEY",
    "SECTION_BY_SLUG",
    "navigation_payload",
    "resolve_section_slug",
    "section_for_key",
]
