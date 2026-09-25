from __future__ import annotations

from html import escape

from backend.security.vault_redaction import redact_value
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



def _broker_picker(
    broker_list: list[dict],
    *,
    selected_broker: str,
    selected_mode: str,
    can_configure: bool,
) -> str:
    from dashboard.enterprise_shell.operator_configuration import broker_row_selectable

    options: list[str] = []
    selectable_count = 0
    for row in broker_list:
        if not isinstance(row, dict):
            continue
        broker = str(row.get("broker") or "").strip().upper()
        if not broker or broker == "PAPER":
            continue
        available = broker_row_selectable(row)
        if available:
            selectable_count += 1
        disabled = "" if available else " disabled"
        selected = " selected" if broker == selected_broker else ""
        state = str(row.get("operational_state") or row.get("status") or "UNAVAILABLE").replace("_", " ")
        label = broker + (" — Available" if available else " — Unavailable: " + state)
        options.append(
            '<option value="' + escape(broker, quote=True) + '"' + disabled + selected + '>'
            + escape(label)
            + '</option>'
        )

    current_label = escape(selected_broker or "NONE")
    if not can_configure:
        return (
            '<section class="mc-broker-select-card mc-broker-select-card-disabled">'
            '<span>Selected Broker</span><strong>' + current_label + '</strong>'
            '<em>Authenticated user session required to change broker</em></section>'
        )

    paper_selected = " selected" if selected_mode == "PAPER" else ""
    read_only_selected = " selected" if selected_mode == "LIVE_READ_ONLY" else ""
    button_disabled = " disabled" if selectable_count == 0 else ""
    return (
        '<details class="mc-broker-select-card" id="mc-selected-broker-card">'
        '<summary><span>Selected Broker</span><strong>' + current_label + '</strong>'
        '<em>Tap to choose and confirm</em></summary>'
        '<div class="mc-broker-picker-body">'
        '<form id="mc-broker-selection-form" class="mc-filter-form">'
        '<label>Preferred broker<select name="broker" required>'
        + ''.join(options)
        + '</select></label>'
        '<label>Broker mode<select name="broker_mode" required>'
        '<option value="PAPER"' + paper_selected + '>Paper</option>'
        '<option value="LIVE_READ_ONLY"' + read_only_selected + '>Live read-only</option>'
        '</select></label>'
        '<label class="mc-confirm-choice"><input type="checkbox" name="confirm_choice" value="YES" required> '
        'I confirm this broker selection before transacting.</label>'
        '<button type="submit"' + button_disabled + '>Confirm Broker Choice</button>'
        '</form>'
        '<p class="mc-muted">Unavailable brokers are greyed out and cannot be selected. '
        'Confirmation records preference only. Execution remains subject to all CSS safety and certification gates.</p>'
        '<p id="mc-broker-selection-result" class="mc-muted" aria-live="polite"></p>'
        '<script>'
        "document.getElementById('mc-broker-selection-form')?.addEventListener('submit', async (ev) => {"
        "ev.preventDefault(); const result=document.getElementById('mc-broker-selection-result');"
        "const body=new URLSearchParams(new FormData(ev.currentTarget));"
        "try { const response=await fetch('/operator-config/broker-selection',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest'},body});"
        "const data=await response.json(); if(!response.ok) throw new Error(data.detail||'Save failed');"
        "result.textContent='Broker choice confirmed. Execution remains blocked until separate transaction gates pass.';"
        "} catch(err){result.textContent=String(err.message||err);} });"
        '</script></div></details>'
    )



def render(state: dict) -> str:
    brokers = section(state, "brokers")
    active = brokers.get("active_broker") if isinstance(brokers.get("active_broker"), dict) else {}
    safety = brokers.get("safety") if isinstance(brokers.get("safety"), dict) else {}
    roles = brokers.get("primary_roles") if isinstance(brokers.get("primary_roles"), dict) else {}
    broker_list = brokers.get("broker_list") if isinstance(brokers.get("broker_list"), list) else []
    operator_selection = brokers.get("operator_selection") if isinstance(brokers.get("operator_selection"), dict) else {}
    auth = state.get("authorization_context") if isinstance(state.get("authorization_context"), dict) else {}
    can_configure = bool(auth.get("authenticated")) and bool(auth.get("active"))
    telemetry = section(state, "broker_telemetry")
    registry = section(state, "broker_registry_console")
    runtime = section(state, "enterprise_broker_runtime")
    runtime_safe = redact_value(runtime)
    balance = section(state, "broker_balance_summary")

    holdings_raw = runtime_safe.get("holdings_readiness") if isinstance(runtime_safe.get("holdings_readiness"), dict) else {}
    provider_raw = runtime_safe.get("provider_health") if isinstance(runtime_safe.get("provider_health"), dict) else {}
    certification_raw = runtime_safe.get("certification") if isinstance(runtime_safe.get("certification"), dict) else {}
    holdings = {
        key: holdings_raw.get(key)
        for key in ("status", "readiness", "freshness", "reason", "source")
        if key in holdings_raw
    }
    provider = {
        key: provider_raw.get(key)
        for key in ("status", "health", "readiness", "freshness", "reason", "source")
        if key in provider_raw
    }
    certification = {
        key: certification_raw.get(key)
        for key in ("outcome", "status", "readiness", "reason", "generated_at")
        if key in certification_raw
    }
    selected_broker = str(operator_selection.get("selected_broker") or active.get("selected_broker") or "NONE").upper()
    selected_mode = str(operator_selection.get("broker_mode") or active.get("broker_mode") or "PAPER").upper()

    return (
        page_header(
            "Broker Management",
            "Sanitized Tier-1 broker posture, account readiness, and advisory-only operating state.",
        )
        + warning_banner(
            "Broker and broker-mode preference can be configured by an authorized administrator. Selection does not arm execution; onboarding mutations remain disabled and execution stays blocked.",
            status="bad",
        )
        + '<nav class="mc-page-jump" aria-label="Broker Management sections">'
          '<a href="#mc-broker-status">Status</a>'
          '<a href="#mc-broker-tier1">Tier-1</a>'
          '<a href="#mc-broker-account">Account</a>'
          '<a href="#mc-broker-evidence">Evidence</a>'
          '</nav>'
        + _broker_picker(
            broker_list,
            selected_broker=selected_broker,
            selected_mode=selected_mode,
            can_configure=can_configure,
        )
        + metric_grid(
            (
                ("Broker Mode", selected_mode, selected_mode),
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
                ("Advisory Readiness", runtime_safe.get("advisory_readiness") or "DATA_DEPENDENCY_BLOCKED", runtime_safe.get("advisory_readiness") or "DATA_DEPENDENCY_BLOCKED"),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Broker Management secondary metrics",
        )
        + _anchor_panel("mc-broker-selection-state", detail_table("Operator Selection Preference", {
            "selected_broker": operator_selection.get("selected_broker") or "NOT_CONFIGURED",
            "broker_mode": operator_selection.get("broker_mode") or "NOT_CONFIGURED",
            "configured_at": operator_selection.get("configured_at") or "UNAVAILABLE",
            "confirmed": operator_selection.get("confirmed") if operator_selection else False,
            "confirmed_at": operator_selection.get("confirmed_at") or "UNAVAILABLE",
            "runtime_application": operator_selection.get("runtime_application") or "UNAVAILABLE",
            "execution_allowed": False,
        }))
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
        + _anchor_panel("mc-broker-registry", detail_table("Broker Registry Console", registry))
        + _anchor_panel("mc-broker-account", detail_table("Account & Balance Snapshot", {
            "balance_status": balance.get("status") or balance.get("availability_state") or "UNAVAILABLE",
            "account_value": balance.get("total_account_value") or balance.get("account_value") or "UNAVAILABLE",
            "holdings_readiness": holdings.get("status") or "UNAVAILABLE",
            "provider_health": provider.get("status") or "UNAVAILABLE",
            "certification": certification.get("outcome") or "NOT_CERTIFIED",
        }))
        + _anchor_panel("mc-broker-safety", detail_table("Broker Safety Snapshot", {
            "selection_editing": "CONTROLLED_CONFIG_ONLY",
            "onboarding_changes": "DISABLED",
            "execution": "BLOCKED",
            "execution_state": "EXECUTION_BLOCKED",
            "safety_status": safety.get("status") or safety.get("execution") or "FAIL_CLOSED",
            "primary_crypto": roles.get("PRIMARY_CRYPTO_BROKER", "UNAVAILABLE"),
            "primary_fx": roles.get("PRIMARY_FX_BROKER", "UNAVAILABLE"),
            "primary_canadian_equities": roles.get("PRIMARY_CANADIAN_EQUITIES_BROKER", "UNAVAILABLE"),
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
        + _evidence_panel("mc-broker-runtime", "Show sanitized provider and readiness evidence",
            detail_table("Enterprise Broker Health", runtime_safe.get("broker_health", {}))
            + detail_table("OAuth Status", runtime_safe.get("oauth_status", []))
            + detail_table("Secret Lease Health", runtime_safe.get("lease_health", []))
            + detail_table("Provider Health", provider)
            + detail_table("Holdings Readiness", holdings)
            + detail_table("Market Data Readiness", runtime_safe.get("market_data_readiness", []))
            + detail_table("Options Readiness", runtime_safe.get("options_readiness", []))
            + detail_table("Advisory Readiness", {"status": runtime_safe.get("advisory_readiness")})
            + detail_table("Certification", certification)
        )
        + '</div>'
    )


__all__ = ["render"]
