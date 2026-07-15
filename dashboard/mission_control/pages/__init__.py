from __future__ import annotations

from dashboard.mission_control.pages import (
    alerts_incidents,
    audit_explainability,
    broker_management,
    certification_readiness,
    documentation_runbooks,
    executive_overview,
    learning_performance,
    market_intelligence,
    options_income,
    portfolio,
    risk_command,
    runtime_operations,
    system_configuration,
    trade_operations,
    users_governance,
)


PAGE_MODULES = {
    "executive_overview": executive_overview,
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


def render_page(section_key: str, state: dict) -> str:
    module = PAGE_MODULES.get(section_key, executive_overview)
    return module.render(state)


__all__ = ["PAGE_MODULES", "render_page"]
