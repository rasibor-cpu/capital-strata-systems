from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_portfolio_command_view(state: Mapping[str, Any]) -> dict[str, Any]:
    portfolio = _mapping(state.get("portfolio"))
    return {
        "status": "UNAVAILABLE" if portfolio.get("equity") == DATA_UNAVAILABLE else "AVAILABLE",
        "equity": portfolio.get("equity", DATA_UNAVAILABLE),
        "cash": portfolio.get("cash", DATA_UNAVAILABLE),
        "buying_power": portfolio.get("buying_power", DATA_UNAVAILABLE),
        "available_capital": portfolio.get("capital_available", DATA_UNAVAILABLE),
        "deployed_capital": portfolio.get("capital_deployed", DATA_UNAVAILABLE),
        "positions": portfolio.get("positions", []),
        "allocation": portfolio.get("asset_allocation", {}),
        "pnl": {
            "realized": portfolio.get("realized_pnl", DATA_UNAVAILABLE),
            "unrealized": portfolio.get("unrealized_pnl", DATA_UNAVAILABLE),
            "net": portfolio.get("net_pnl", DATA_UNAVAILABLE),
            "by_asset_class": portfolio.get("pnl_by_asset_class", {}),
            "by_strategy": portfolio.get("pnl_by_strategy", DATA_UNAVAILABLE),
        },
        "drawdown": portfolio.get("drawdown", DATA_UNAVAILABLE),
        "collateral": portfolio.get("collateral_utilization", DATA_UNAVAILABLE),
        "capital_utilization": portfolio.get("capital_deployed", DATA_UNAVAILABLE),
        "read_only": True,
        **_metadata(state, "portfolio_command_view"),
    }


def build_performance_panel(state: Mapping[str, Any]) -> dict[str, Any]:
    learning = _mapping(state.get("learning"))
    trading = _mapping(state.get("trading"))
    portfolio = _mapping(state.get("portfolio"))
    return {
        "status": "AVAILABLE" if any(learning.get(key) != DATA_UNAVAILABLE for key in ("expectancy", "win_rate", "profit_factor")) else "UNAVAILABLE",
        "expectancy": learning.get("expectancy", DATA_UNAVAILABLE),
        "win_rate": learning.get("win_rate", DATA_UNAVAILABLE),
        "average_gain": learning.get("average_gain", DATA_UNAVAILABLE),
        "average_loss": learning.get("average_loss", DATA_UNAVAILABLE),
        "profit_factor": learning.get("profit_factor", DATA_UNAVAILABLE),
        "sharpe": learning.get("sharpe", DATA_UNAVAILABLE),
        "capital_efficiency": learning.get("capital_efficiency", portfolio.get("capital_efficiency", DATA_UNAVAILABLE)),
        "strategy_ranking": learning.get("strategy_rankings", []),
        "trade_quality": trading.get("execution_quality", DATA_UNAVAILABLE),
        "read_only": True,
        **_metadata(state, "performance_panel"),
    }


def build_options_income_panel(state: Mapping[str, Any]) -> dict[str, Any]:
    options = _mapping(state.get("options_income"))
    status = options.get("status", DATA_UNAVAILABLE)
    deployment = str(options.get("deployment_state") or "").upper()
    # Phase 177D precise semantics: deployed advisory states are not "NOT YET DEPLOYED"
    deployed = deployment == "DEPLOYED" or status not in {
        DATA_UNAVAILABLE,
        "UNAVAILABLE",
        "NOT_DEPLOYED",
        "NOT YET DEPLOYED",
        "",
        None,
    }
    panel_status = status if deployed else "NOT YET DEPLOYED"
    if deployed and status in {"ADVISORY_ONLY", "DATA_DEPENDENCY_BLOCKED", "READY", "NO_CURRENT_OPPORTUNITIES", "PARTIAL_DATA"}:
        panel_status = status
    return {
        "status": panel_status,
        "deployed": bool(deployed),
        "deployment_state": options.get("deployment_state", "UNKNOWN"),
        "opportunity_count": options.get("opportunity_count", len(options.get("opportunities", []) or [])),
        "opportunities": options.get("opportunities", []),
        "premium_accounting": options.get("premium_accounting", DATA_UNAVAILABLE),
        "collateral": options.get("collateral", DATA_UNAVAILABLE),
        "greeks": options.get("greeks", DATA_UNAVAILABLE),
        "assignment_risk": options.get("assignment_risk", DATA_UNAVAILABLE),
        "volatility_risk": options.get("volatility_risk", DATA_UNAVAILABLE),
        "rolling_recommendations": options.get("rolling_recommendations", []),
        "income_targets": options.get("income_targets", DATA_UNAVAILABLE),
        "run_rate": options.get("run_rate", DATA_UNAVAILABLE),
        "certification": options.get("certification", DATA_UNAVAILABLE),
        "operational_readiness": options.get("operational_readiness", DATA_UNAVAILABLE),
        "missing_dependencies": options.get("missing_dependencies", []),
        "state_hash": options.get("state_hash", DATA_UNAVAILABLE),
        "generated_at": options.get("generated_at", DATA_UNAVAILABLE),
        "last_successful_refresh": options.get("last_successful_refresh", DATA_UNAVAILABLE),
        "provenance": options.get("provenance", {}),
        "advisory_only": True,
        "execution_blocked": True,
        "read_only": True,
        **_metadata(state, "options_income_panel"),
    }


def _metadata(state: Mapping[str, Any], source_module: str) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    snapshot = _mapping(state.get("runtime_snapshot"))
    freshness = _mapping(state.get("freshness"))
    return {
        "source": runtime.get("source", snapshot.get("source", DATA_UNAVAILABLE)),
        "source_module": f"dashboard.mission_control.{source_module}",
        "provenance": snapshot.get("provenance", {}),
        "generated_at": state.get("generated_at", DATA_UNAVAILABLE),
        "freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_options_income_panel", "build_performance_panel", "build_portfolio_command_view"]
