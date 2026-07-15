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

SECTION_BY_KEY = {section.key: section for section in MISSION_CONTROL_SECTIONS}


def section_for_key(key: str | None) -> MissionControlSection:
    return SECTION_BY_KEY.get(str(key or "").strip().lower(), MISSION_CONTROL_SECTIONS[0])


def navigation_payload() -> list[dict[str, str]]:
    return [section.as_dict() for section in MISSION_CONTROL_SECTIONS]


__all__ = [
    "MISSION_CONTROL_SECTIONS",
    "MissionControlSection",
    "navigation_payload",
    "section_for_key",
]
