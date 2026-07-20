"""Phase 178 — read-only Executive Intelligence financial adapter."""

from __future__ import annotations

from typing import Any

from backend.financial_reporting.models import deep_freeze_dict


def executive_intelligence_financial_provider(
    executive_package: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Stable EI-facing view of financial summary + narrative.

    Does not modify financial data. No autonomous execution.
    """
    pkg = executive_package if isinstance(executive_package, dict) else {}
    summary = pkg.get("financial_summary") if isinstance(pkg.get("financial_summary"), dict) else {}
    narrative = pkg.get("narrative") if isinstance(pkg.get("narrative"), dict) else {}
    sections = narrative.get("sections") if isinstance(narrative.get("sections"), dict) else {}
    actions = pkg.get("management_actions") if isinstance(pkg.get("management_actions"), list) else []
    run = pkg.get("profitability_run_rate") if isinstance(pkg.get("profitability_run_rate"), dict) else {}

    headline = sections.get("executive_conclusion") or "Financial summary unavailable."
    return deep_freeze_dict(
        {
            "schema_version": "css.ei_financial_provider.v1",
            "financial_headline": headline,
            "profitability_state": {
                "net_profit": summary.get("net_profit"),
                "operating_profit": summary.get("operating_profit"),
                "traffic_light": summary.get("profitability_traffic_light") or "NOT_AVAILABLE",
            },
            "run_rate_requirement": {
                "target_profit": summary.get("target_profit"),
                "required_daily_run_rate": summary.get("required_daily_run_rate"),
                "actual_daily_run_rate": summary.get("actual_daily_run_rate"),
                "projected_period_end_profit": summary.get("projected_period_end_profit"),
            },
            "major_variances": {
                "projected_target_variance": summary.get("projected_target_variance"),
                "target_achieved_percentage": summary.get("target_achieved_percentage"),
                "remaining_profit_required": summary.get("remaining_profit_required")
                or run.get("remaining_profit_required"),
            },
            "cash_direction": sections.get("cash_position"),
            "reporting_readiness": summary.get("reporting_readiness") or "NOT_READY",
            "management_actions": list(actions),
            "advisory_only": True,
            "trading_impact": False,
            "mutable": False,
        }
    )
