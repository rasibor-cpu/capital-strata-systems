from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels, warning_banner


def render(state: dict) -> str:
    brokers = section(state, "brokers")
    active = brokers.get("active_broker", {}) if isinstance(brokers.get("active_broker"), dict) else {}
    selection = brokers.get("selection", {}) if isinstance(brokers.get("selection"), dict) else {}
    onboarding = brokers.get("onboarding", {}) if isinstance(brokers.get("onboarding"), dict) else {}
    safety = brokers.get("safety", {}) if isinstance(brokers.get("safety"), dict) else {}
    telemetry = section(state, "broker_telemetry")
    return (
        page_header("Broker Management", "Read-only active broker state, broker registry, selection preview, onboarding shell, capabilities, and safety controls.")
        + warning_banner("Broker selection and onboarding controls are disabled. Runtime broker state is display-only.", status="bad")
        + metric_grid(
            (
                ("Selected Broker", active.get("selected_broker"), active.get("selected_broker")),
                ("Broker Mode", active.get("broker_mode"), active.get("broker_mode")),
                ("Connection", active.get("connection_status"), active.get("connection_status")),
                ("Authentication", active.get("authentication_status"), active.get("authentication_status")),
                ("Account", active.get("account_status"), active.get("account_status")),
                ("Market Data", active.get("market_data_status"), active.get("market_data_status")),
                ("Balance", active.get("balance_status"), active.get("balance_status")),
                ("Buying Power", active.get("buying_power_status"), "neutral"),
                ("Margin", active.get("margin_status"), active.get("margin_status")),
                ("Execution Scope", active.get("execution_scope"), active.get("execution_scope")),
            )
        )
        + split_panels(
            detail_table("Active Broker", active),
            detail_table("Broker Telemetry", {
                "broker": telemetry.get("broker"),
                "authentication": telemetry.get("authentication"),
                "connection": telemetry.get("connection"),
                "transport": telemetry.get("transport"),
                "latency": telemetry.get("latency"),
                "market_data_freshness": telemetry.get("market_data_freshness"),
                "heartbeat": telemetry.get("heartbeat"),
                "api_availability": telemetry.get("api_availability"),
                "rate_limits": telemetry.get("rate_limits"),
                "products": telemetry.get("products"),
                "account_readiness": telemetry.get("account_readiness"),
                "overall_health": telemetry.get("overall_health"),
                "source": telemetry.get("source"),
                "state_hash": telemetry.get("state_hash"),
            }),
            detail_table("Broker List", brokers.get("broker_list", [])),
            detail_table("Selection Preview", selection),
            detail_table("Onboarding Shell", onboarding),
            detail_table("Broker Safety", safety),
        )
    )
