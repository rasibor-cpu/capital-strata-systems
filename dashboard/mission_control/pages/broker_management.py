from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels, warning_banner


def render(state: dict) -> str:
    brokers = section(state, "brokers")
    active = brokers.get("active_broker", {}) if isinstance(brokers.get("active_broker"), dict) else {}
    selection = brokers.get("selection", {}) if isinstance(brokers.get("selection"), dict) else {}
    onboarding = brokers.get("onboarding", {}) if isinstance(brokers.get("onboarding"), dict) else {}
    safety = brokers.get("safety", {}) if isinstance(brokers.get("safety"), dict) else {}
    roles = brokers.get("primary_roles", {}) if isinstance(brokers.get("primary_roles"), dict) else {}
    telemetry = section(state, "broker_telemetry")
    registry = section(state, "broker_registry_console")
    broker_list = brokers.get("broker_list", []) if isinstance(brokers.get("broker_list"), list) else []
    # Compact Tier-1 status table for Mission Control (Role + Status)
    tier_rows = []
    for row in broker_list:
        if not isinstance(row, dict):
            continue
        if row.get("broker") == "PAPER":
            continue
        tier_rows.append(
            {
                "Broker": row.get("broker"),
                "Role": row.get("role") or row.get("broker_role"),
                "Operational State": row.get("operational_state") or row.get("status"),
                "Readiness": row.get("readiness"),
                "Certification": row.get("certification"),
                "Latency": row.get("latency"),
                "Authentication": row.get("authentication"),
                "Market Data": row.get("market_data"),
                "Account": row.get("account") or row.get("account_data"),
                "Execution": row.get("execution"),
                "Last Sync": row.get("last_sync"),
            }
        )
    return (
        page_header("Broker Management", "Phase 177C canonical Tier-1 registry — Coinbase, Binance, OANDA, Questrade. IBKR removed from roadmap. Display-only.")
        + warning_banner("Broker selection and onboarding controls are disabled. LIVE_READ_ONLY only — execution blocked.", status="bad")
        + metric_grid(
            (
                ("Selected Broker", active.get("selected_broker"), active.get("selected_broker")),
                ("Broker Mode", active.get("broker_mode"), active.get("broker_mode")),
                ("Primary Crypto", roles.get("PRIMARY_CRYPTO_BROKER", "COINBASE"), "neutral"),
                ("Primary FX", roles.get("PRIMARY_FX_BROKER", "OANDA"), "neutral"),
                ("Primary CA Equities", roles.get("PRIMARY_CANADIAN_EQUITIES_BROKER", "QUESTRADE"), "neutral"),
                ("Connection", active.get("connection_status"), active.get("connection_status")),
                ("Authentication", active.get("authentication_status"), active.get("authentication_status")),
                ("Account", active.get("account_status"), active.get("account_status")),
                ("Market Data", active.get("market_data_status"), active.get("market_data_status")),
                ("Execution Scope", active.get("execution_scope"), active.get("execution_scope")),
            )
        )
        + split_panels(
            detail_table("Tier-1 Broker Status (Role + State)", tier_rows),
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
            detail_table("Broker List", broker_list),
            detail_table("Broker Registry Console", {
                "registered_brokers": registry.get("registered_brokers"),
                "active_broker": registry.get("active_broker"),
                "capabilities": registry.get("capabilities"),
                "certification": registry.get("certification"),
                "readiness": registry.get("readiness"),
                "broker_status": registry.get("broker_status"),
                "supported_products": registry.get("supported_products"),
                "editing_enabled": registry.get("editing_enabled"),
                "protected_fields_redacted": registry.get("protected_fields_redacted"),
            }),
            detail_table("Selection Preview", selection),
            detail_table("Onboarding Shell", onboarding),
            detail_table("Broker Safety", safety),
        )
    )
