from __future__ import annotations

from dashboard.mission_control.pages._components import (
    detail_table,
    metric_grid,
    page_header,
    section,
    warning_banner,
)


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
    )


def _tier_summary(rows: object) -> dict[str, str]:
    if not isinstance(rows, list):
        return {}
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("broker") == "PAPER":
            continue
        broker = str(row.get("broker") or "UNAVAILABLE")
        role = str(row.get("role") or row.get("broker_role") or "UNAVAILABLE").replace("_", " ")
        state = str(row.get("operational_state") or row.get("status") or "UNAVAILABLE").replace("_", " ")
        readiness = str(row.get("readiness") or "UNAVAILABLE").replace("_", " ")
        certification = str(row.get("certification") or "UNAVAILABLE").replace("_", " ")
        execution = str(row.get("execution") or "BLOCKED").replace("_", " ")
        result[broker] = (
            f"{role} · {state} · readiness {readiness} · "
            f"certification {certification} · execution {execution}"
        )
    return result


def render(state: dict) -> str:
    brokers = section(state, "brokers")
    active = brokers.get("active_broker") if isinstance(brokers.get("active_broker"), dict) else {}
    safety = brokers.get("safety") if isinstance(brokers.get("safety"), dict) else {}
    roles = brokers.get("primary_roles") if isinstance(brokers.get("primary_roles"), dict) else {}
    broker_list = brokers.get("broker_list") if isinstance(brokers.get("broker_list"), list) else []
    telemetry = section(state, "broker_telemetry")
    runtime = section(state, "enterprise_broker_runtime")
    balance = section(state, "broker_balance_summary")

    holdings = runtime.get("holdings_readiness") if isinstance(runtime.get("holdings_readiness"), dict) else {}
    provider = runtime.get("provider_health") if isinstance(runtime.get("provider_health"), dict) else {}
    certification = runtime.get("certification") if isinstance(runtime.get("certification"), dict) else {}

    return (
        page_header(
            "Broker Management",
            "Sanitized Tier-1 broker posture, account readiness, and advisory-only operating state.",
        )
        + warning_banner(
            "Broker selection and onboarding controls are disabled. Execution remains blocked.",
            status="bad",
        )
        + '<nav class="mc-page-jump" aria-label="Broker Management sections">'
          '<a href="#mc-broker-status">Status</a>'
          '<a href="#mc-broker-tier1">Tier-1</a>'
          '<a href="#mc-broker-account">Account</a>'
          '<a href="#mc-broker-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Selected Broker", active.get("selected_broker"), active.get("selected_broker")),
                ("Broker Mode", active.get("broker_mode"), active.get("broker_mode")),
                ("Connection", active.get("connection_status"), active.get("connection_status")),
                ("Execution", "BLOCKED", "blocked"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-broker-priority",
            aria_label="Broker Management priority",
        )
        + metric_grid(
            (
                ("Authentication", active.get("authentication_status"), active.get("authentication_status")),
                ("Account", active.get("account_status"), active.get("account_status")),
                ("Market Data", active.get("market_data_status"), active.get("market_data_status")),
                ("Advisory Readiness", runtime.get("advisory_readiness") or "DATA_DEPENDENCY_BLOCKED", runtime.get("advisory_readiness") or "DATA_DEPENDENCY_BLOCKED"),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Broker Management secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-broker-status", detail_table("Broker Status Snapshot", {
            "selected_broker": active.get("selected_broker"),
            "broker_mode": active.get("broker_mode"),
            "connection_status": active.get("connection_status"),
            "authentication_status": active.get("authentication_status"),
            "account_status": active.get("account_status"),
            "market_data_status": active.get("market_data_status"),
            "execution_scope": active.get("execution_scope") or "BLOCKED",
        }))
        + _anchor_panel("mc-broker-tier1", detail_table("Tier-1 Broker Snapshot", _tier_summary(broker_list)))
        + _anchor_panel("mc-broker-account", detail_table("Account & Balance Snapshot", {
            "balance_status": balance.get("status") or balance.get("availability_state") or "UNAVAILABLE",
            "account_value": balance.get("total_account_value") or balance.get("account_value") or "UNAVAILABLE",
            "holdings_readiness": holdings.get("status") or "UNAVAILABLE",
            "provider_health": provider.get("status") or "UNAVAILABLE",
            "certification": certification.get("outcome") or "NOT_CERTIFIED",
        }))
        + _anchor_panel("mc-broker-safety", detail_table("Broker Safety Snapshot", {
            "selection_editing": "DISABLED",
            "onboarding_changes": "DISABLED",
            "execution": "BLOCKED",
            "safety_status": safety.get("status") or safety.get("execution") or "FAIL_CLOSED",
            "primary_crypto": roles.get("PRIMARY_CRYPTO_BROKER", "COINBASE"),
            "primary_fx": roles.get("PRIMARY_FX_BROKER", "OANDA"),
            "primary_canadian_equities": roles.get("PRIMARY_CANADIAN_EQUITIES_BROKER", "QUESTRADE"),
        }))
        + _evidence_panel("mc-broker-evidence", "Show sanitized broker telemetry", detail_table("Broker Telemetry", {
            "broker": telemetry.get("broker"),
            "connection": telemetry.get("connection"),
            "transport": telemetry.get("transport"),
            "latency": telemetry.get("latency"),
            "market_data_freshness": telemetry.get("market_data_freshness"),
            "heartbeat": telemetry.get("heartbeat"),
            "api_availability": telemetry.get("api_availability"),
            "overall_health": telemetry.get("overall_health"),
        }))
        + _evidence_panel("mc-broker-runtime", "Show sanitized provider and readiness evidence", detail_table("Provider & Readiness", {
            "provider_health": provider.get("status") or "UNAVAILABLE",
            "holdings_readiness": holdings.get("status") or "UNAVAILABLE",
            "market_data_readiness": runtime.get("market_data_readiness"),
            "options_readiness": runtime.get("options_readiness"),
            "advisory_readiness": runtime.get("advisory_readiness"),
            "certification": certification.get("outcome"),
        }))
        + '</div>'
    )


__all__ = ["render"]
