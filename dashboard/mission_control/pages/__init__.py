from __future__ import annotations

from dashboard.mission_control.pages import (
    alerts_incidents,
    audit_explainability,
    broker_management,
    certification_readiness,
    credential_governance,
    documentation_runbooks,
    enterprise_identity,
    enterprise_governance,
    enterprise_oauth,
    executive_overview,
    learning_performance,
    market_intelligence,
    options_income,
    portfolio,
    production_readiness,
    reports_center,
    risk_command,
    runtime_operations,
    system_configuration,
    trade_operations,
    users_governance,
)


PAGE_MODULES = {
    "executive_overview": executive_overview,
    "reports_center": reports_center,
    "runtime_operations": runtime_operations,
    "trade_operations": trade_operations,
    "portfolio": portfolio,
    "market_intelligence": market_intelligence,
    "risk_command": risk_command,
    "options_income": options_income,
    "broker_management": broker_management,
    "alerts_incidents": alerts_incidents,
    "certification_readiness": certification_readiness,
    "audit_explainability": audit_explainability,
    "learning_performance": learning_performance,
    "users_governance": users_governance,
    "system_configuration": system_configuration,
    "documentation_runbooks": documentation_runbooks,
}

AUXILIARY_PAGE_MODULES = {
    "credential_governance": credential_governance,
    "enterprise_identity": enterprise_identity,
    "enterprise_governance": enterprise_governance,
    "enterprise_oauth": enterprise_oauth,
    "production_readiness": production_readiness,
}

ALL_PAGE_MODULES = {
    **PAGE_MODULES,
    **AUXILIARY_PAGE_MODULES,
}


def render_page(section_key: str, state: dict) -> str:
    module = ALL_PAGE_MODULES.get(section_key)
    if module is None:
        raise KeyError(f"unknown_mission_control_page:{section_key}")
    return module.render(state)


__all__ = ["ALL_PAGE_MODULES", "AUXILIARY_PAGE_MODULES", "PAGE_MODULES", "render_page"]
