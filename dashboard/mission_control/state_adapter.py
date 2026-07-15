from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.mission_control.mock_data import mission_control_mock_dashboard_payload
from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE, build_frontend_payload


def frontend_payload_from_runtime(
    dashboard_state: Any = None,
    *,
    allow_mock: bool = True,
) -> dict[str, Any]:
    if isinstance(dashboard_state, Mapping) and isinstance(dashboard_state.get("frontend_payload"), Mapping):
        payload = dict(dashboard_state["frontend_payload"])
        payload["mission_control_data_source"] = str(dashboard_state.get("source") or payload.get("mission_control_data_source") or "RUNTIME").upper()
        payload["mission_control_mock_data"] = _is_mock_source(dashboard_state)
        payload["mission_control_dashboard_state_available"] = True
        return payload
    if isinstance(dashboard_state, Mapping) and dashboard_state.get("payload_schema") == "css.frontend.contract.v1" and isinstance(dashboard_state.get("sections"), Mapping):
        payload = dict(dashboard_state)
        payload["mission_control_data_source"] = str(payload.get("mission_control_data_source") or "RUNTIME").upper()
        payload["mission_control_mock_data"] = _is_mock_source(dashboard_state)
        payload["mission_control_dashboard_state_available"] = True
        return payload

    source = dashboard_state if dashboard_state is not None else None
    if source is None and allow_mock:
        source = mission_control_mock_dashboard_payload()
    payload = build_frontend_payload(source or {})
    if _is_mock_source(source):
        data_source = "MOCK"
    elif source is None:
        data_source = "UNAVAILABLE"
    else:
        data_source = "RUNTIME"
    payload["mission_control_data_source"] = data_source
    payload["mission_control_mock_data"] = _is_mock_source(source)
    payload["mission_control_dashboard_state_available"] = source is not None
    return payload


def _is_mock_source(source: Any) -> bool:
    if isinstance(source, Mapping):
        return bool(source.get("mock_data") or source.get("mission_control_mock_data") or source.get("source") == "DEMO")
    return False


def section(payload: Mapping[str, Any], name: str) -> dict[str, Any]:
    sections = payload.get("sections")
    if isinstance(sections, Mapping):
        value = sections.get(name)
        if isinstance(value, Mapping):
            return dict(value)
    return {"status": DATA_UNAVAILABLE}


def build_broker_registry(active_broker: Mapping[str, Any]) -> list[dict[str, Any]]:
    selected = str(active_broker.get("selected_broker", active_broker.get("broker", "NONE"))).upper()
    mode = str(active_broker.get("broker_mode", "paper")).lower()
    broker_health = str(active_broker.get("broker_health", "UNAVAILABLE"))
    profile = _profile_metadata(active_broker)
    registry = [
        {
            "broker": "COINBASE",
            "status": broker_health if selected == "COINBASE" else "SUPPORTED",
            "mode": mode if selected == "COINBASE" else "available",
            "capabilities": ["accounts", "balances", "portfolios", "products", "market_data"],
            "credentials_present": active_broker.get("credential_status", "UNKNOWN") if selected == "COINBASE" else "UNKNOWN",
            "authentication": active_broker.get("authentication_status", "UNKNOWN") if selected == "COINBASE" else "UNKNOWN",
            "market_data": active_broker.get("market_data_status", "UNKNOWN") if selected == "COINBASE" else "UNKNOWN",
            "account_data": active_broker.get("account_data_health", "UNKNOWN") if selected == "COINBASE" else "UNKNOWN",
            "readiness": active_broker.get("overall_status", broker_health) if selected == "COINBASE" else "UNCONFIGURED",
            "profile": profile if selected == "COINBASE" else _inactive_profile(),
            "priority": 1,
            "supported_assets": ["CRYPTO"],
            "supported_strategies": ["spot_read_only", "future_pilot_candidate"],
            "selected": selected == "COINBASE",
        },
        {
            "broker": "OANDA",
            "status": broker_health if selected == "OANDA" else "SUPPORTED",
            "mode": mode if selected == "OANDA" else "available",
            "capabilities": ["account_summary", "pricing", "instruments", "market_data"],
            "credentials_present": active_broker.get("credential_status", "UNKNOWN") if selected == "OANDA" else "UNKNOWN",
            "authentication": active_broker.get("authentication_status", "UNKNOWN") if selected == "OANDA" else "UNKNOWN",
            "market_data": active_broker.get("market_data_status", "UNKNOWN") if selected == "OANDA" else "UNKNOWN",
            "account_data": active_broker.get("account_data_health", "UNKNOWN") if selected == "OANDA" else "UNKNOWN",
            "readiness": active_broker.get("overall_status", broker_health) if selected == "OANDA" else "UNCONFIGURED",
            "profile": profile if selected == "OANDA" else _inactive_profile(),
            "priority": 2,
            "supported_assets": ["FOREX"],
            "supported_strategies": ["fx_read_only", "future_pilot_candidate"],
            "selected": selected == "OANDA",
        },
        {
            "broker": "IBKR",
            "status": "FUTURE_ADAPTER",
            "mode": "not_configured",
            "capabilities": ["equities", "options", "futures"],
            "credentials_present": "UNKNOWN",
            "authentication": "NOT_TESTED",
            "market_data": "UNAVAILABLE",
            "account_data": "UNAVAILABLE",
            "readiness": "UNCONFIGURED",
            "priority": 3,
            "supported_assets": ["STOCK", "ETF", "OPTION", "FUTURE"],
            "supported_strategies": ["future_options_income"],
            "selected": selected == "IBKR",
            "profile": _inactive_profile(),
        },
        {
            "broker": "PAPER",
            "status": "AVAILABLE",
            "mode": "paper",
            "capabilities": ["simulation", "paper_positions", "paper_orders"],
            "credentials_present": "NOT_REQUIRED",
            "authentication": "NOT_REQUIRED",
            "market_data": "SIMULATION",
            "account_data": "SIMULATION",
            "readiness": "READY_FOR_PAPER",
            "priority": 4,
            "supported_assets": ["STOCK", "ETF", "OPTION", "FOREX", "CRYPTO"],
            "supported_strategies": ["paper_only"],
            "selected": selected in {"PAPER", "DEMO", "NONE"},
            "profile": profile if selected in {"PAPER", "DEMO", "NONE"} else _inactive_profile(profile_name="PAPER"),
        },
    ]
    return registry


def _profile_metadata(active_broker: Mapping[str, Any]) -> dict[str, Any]:
    profile = active_broker.get("broker_environment_profile")
    if not isinstance(profile, Mapping):
        canonical = active_broker.get("canonical_broker_runtime_state")
        if isinstance(canonical, Mapping):
            profile = canonical.get("environment_evidence")
    source = dict(profile) if isinstance(profile, Mapping) else {}
    return {
        "profile": str(source.get("profile", active_broker.get("profile", "UNSELECTED"))),
        "environment": str(source.get("environment", active_broker.get("environment", active_broker.get("broker_mode", "paper")))),
        "permissions_classification": str(source.get("permissions_classification", active_broker.get("permissions_classification", "UNKNOWN"))),
        "profile_fingerprint": str(source.get("profile_fingerprint", active_broker.get("profile_fingerprint", ""))),
        "contamination_status": str(source.get("status", active_broker.get("contamination_status", "UNKNOWN"))),
        "contamination_keys": list(source.get("contamination_keys", active_broker.get("contamination_keys", [])) or []),
        "credential_values_redacted": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def _inactive_profile(*, profile_name: str = "UNSELECTED") -> dict[str, Any]:
    return {
        "profile": profile_name,
        "environment": "inactive",
        "permissions_classification": "NOT_APPLICABLE",
        "profile_fingerprint": "",
        "contamination_status": "NOT_APPLICABLE",
        "contamination_keys": [],
        "credential_values_redacted": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


__all__ = [
    "build_broker_registry",
    "frontend_payload_from_runtime",
    "section",
]
