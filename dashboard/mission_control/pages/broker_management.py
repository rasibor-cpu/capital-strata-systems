from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels, warning_banner


def render(state: dict) -> str:
    authorization = state.get("authorization_context") if isinstance(state.get("authorization_context"), dict) else {}
    diagnostics_allowed = bool(
        authorization.get("authenticated")
        and authorization.get("active")
        and str(authorization.get("role") or "").upper() in {"SUPER_USER", "ADMIN"}
    )
    if diagnostics_allowed:
        enterprise_runtime = section(state, "enterprise_broker_runtime")
        runtime_health = (
            enterprise_runtime.get("broker_health")
            if isinstance(enterprise_runtime.get("broker_health"), dict)
            else {}
        )
        bindings = runtime_health.get("bindings") if isinstance(runtime_health.get("bindings"), list) else []
        questrade_binding = next(
            (
                row
                for row in bindings
                if isinstance(row, dict) and row.get("broker") == "QUESTRADE"
            ),
            {},
        )
        questrade_panel = {
            "Operational State": runtime_health.get("status", "CONFIGURATION_REQUIRED"),
            "Secure Configuration": "ENTERPRISE_HANDLES_ONLY"
            if questrade_binding
            else "CONFIGURATION_REQUIRED",
            "Authorization State": (
                "OAUTH_HANDLE_BOUND"
                if questrade_binding.get("oauth_handle")
                else "CONFIGURATION_REQUIRED"
            ),
            "Token Health": enterprise_runtime.get("secret_lease_health", []),
            "API Server Health": enterprise_runtime.get("provider_health", {}),
            "Account Selection": enterprise_runtime.get("holdings_readiness", {}).get(
                "account_id_sanitized"
            )
            if isinstance(enterprise_runtime.get("holdings_readiness"), dict)
            else None,
            "Balances": enterprise_runtime.get("holdings_readiness", {}).get("status")
            if isinstance(enterprise_runtime.get("holdings_readiness"), dict)
            else None,
            "Holdings": enterprise_runtime.get("holdings_readiness", {}).get("status")
            if isinstance(enterprise_runtime.get("holdings_readiness"), dict)
            else None,
            "Market Data": enterprise_runtime.get("market_data_readiness", []),
            "Option Chain": enterprise_runtime.get("options_readiness", []),
            "Certification": (
                enterprise_runtime.get("certification", {}).get("outcome")
                if isinstance(enterprise_runtime.get("certification"), dict)
                else "NOT_CERTIFIED"
            ),
            "Required Action": "Resolve certification blockers",
            "OAuth Launch Enabled": False,
            "Credential Form Enabled": False,
            "Execution": "EXECUTION_BLOCKED",
        }
    else:
        questrade_panel = {
            "Status": "AUTHENTICATION_REQUIRED",
            "Detail": "Authenticate to view Questrade configuration and token-health metadata",
            "Execution": "EXECUTION_BLOCKED",
        }
    brokers = section(state, "brokers")
    active = brokers.get("active_broker", {}) if isinstance(brokers.get("active_broker"), dict) else {}
    selection = brokers.get("selection", {}) if isinstance(brokers.get("selection"), dict) else {}
    onboarding = brokers.get("onboarding", {}) if isinstance(brokers.get("onboarding"), dict) else {}
    safety = brokers.get("safety", {}) if isinstance(brokers.get("safety"), dict) else {}
    roles = brokers.get("primary_roles", {}) if isinstance(brokers.get("primary_roles"), dict) else {}
    telemetry = section(state, "broker_telemetry")
    registry = section(state, "broker_registry_console")
    enterprise_runtime = section(state, "enterprise_broker_runtime")
    balance_summary = section(state, "broker_balance_summary")
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
                "Required Action": row.get("recommended_action"),
                "Expected Condition": row.get("expected_condition"),
                "Retryable": row.get("retryable"),
                "Latency": row.get("latency"),
                "Freshness": row.get("freshness"),
                "Authentication": row.get("authentication"),
                "Market Data": row.get("market_data"),
                "Option Chain": _capability_state(row, "OPTION_CHAIN"),
                "Account": row.get("account") or row.get("account_data"),
                "Execution": row.get("execution"),
                "Last Operation": row.get("last_successful_operation") or row.get("last_sync"),
            }
        )
    return (
        page_header("Broker Management", "Canonical Tier-1 states with secure Questrade read-only onboarding — execution remains blocked.")
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
            detail_table("Canonical Broker Balance Summary", balance_summary),
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
            detail_table("Capability-Specific States", {
                str(row.get("broker")): row.get("capability_states")
                for row in broker_list
                if isinstance(row, dict) and row.get("broker") != "PAPER"
            }),
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
            detail_table("Questrade Secure Read-Only Onboarding", questrade_panel),
            detail_table("Enterprise Broker Health", enterprise_runtime.get("broker_health", {})),
            detail_table("OAuth Status", enterprise_runtime.get("oauth_status", [])),
            detail_table("Secret Lease Health", enterprise_runtime.get("secret_lease_health", [])),
            detail_table(
                "Credential Governance Summary",
                enterprise_runtime.get("credential_governance_summary", {}),
            ),
            detail_table("Provider Health", enterprise_runtime.get("provider_health", {})),
            detail_table("Holdings Readiness", enterprise_runtime.get("holdings_readiness", {})),
            detail_table("Market Data Readiness", enterprise_runtime.get("market_data_readiness", [])),
            detail_table("Options Readiness", enterprise_runtime.get("options_readiness", [])),
            detail_table(
                "Advisory Readiness",
                {"status": enterprise_runtime.get("advisory_readiness", "DATA_DEPENDENCY_BLOCKED")},
            ),
            detail_table("Broker Safety", safety),
        )
    )


def _capability_state(row: dict, capability: str) -> str:
    states = row.get("capability_states") if isinstance(row.get("capability_states"), dict) else {}
    result = states.get(capability) if isinstance(states.get(capability), dict) else {}
    return str(result.get("state") or "UNAVAILABLE")
