from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, warning_banner


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
    )


def render(state: dict) -> str:
    cert = section(state, "certification")
    summary = section(state, "governance_summary_console")
    final = section(state, "final_certification")
    return (
        page_header("Certification and Readiness", "Read-only RC1, operational, Options Income, broker, runtime, live-disable proof, blockers, and prerequisites.")
        + warning_banner("READY_FOR_CONTROLLED_RC1_RUNTIME is not READY_FOR_LIVE_TRADING.", status="warn")
        + '<nav class="mc-page-jump" aria-label="Certification sections">'
          '<a href="#mc-cert-status">Status</a>'
          '<a href="#mc-cert-blockers">Blockers</a>'
          '<a href="#mc-cert-governance">Governance</a>'
          '<a href="#mc-cert-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("RC1 Platform", cert.get("rc1_platform_certification"), cert.get("rc1_platform_certification")),
                ("RC1 Operational", cert.get("rc1_operational_readiness"), cert.get("rc1_operational_readiness")),
                ("Broker Readiness", cert.get("broker_readiness"), cert.get("broker_readiness")),
                ("Live Trading", cert.get("ready_for_live_trading"), cert.get("ready_for_live_trading")),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-cert-priority",
            aria_label="Certification priority",
        )
        + metric_grid(
            (
                ("Options Income", cert.get("options_income_certification"), cert.get("options_income_certification")),
                ("Runtime Readiness", cert.get("runtime_readiness"), cert.get("runtime_readiness")),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Certification secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-cert-status", detail_table("Readiness Snapshot", {
            "ready_for_controlled_rc1_runtime": cert.get("ready_for_controlled_rc1_runtime"),
            "ready_for_live_trading": cert.get("ready_for_live_trading"),
            "rc1_platform_certification": cert.get("rc1_platform_certification"),
            "rc1_operational_readiness": cert.get("rc1_operational_readiness"),
            "broker_readiness": cert.get("broker_readiness"),
            "runtime_readiness": cert.get("runtime_readiness"),
        }))
        + _anchor_panel("mc-cert-blockers", detail_table("Blockers & Warnings", {
            "blockers": cert.get("blockers"),
            "warnings": cert.get("warnings"),
        }))
        + _anchor_panel("mc-cert-governance-summary", detail_table("Governance Summary", summary))
        + _anchor_panel("mc-cert-governance", detail_table("Governance Snapshot", {
            "security_posture": summary.get("security_posture"),
            "audit_posture": summary.get("audit_posture"),
            "approval_posture": summary.get("approval_posture"),
            "configuration_posture": summary.get("configuration_posture"),
            "certification_posture": summary.get("certification_posture"),
            "write_routes_enabled": summary.get("write_routes_enabled"),
            "operator_actions_enabled": summary.get("operator_actions_enabled"),
        }))
        + _evidence_panel("mc-cert-evidence", "Show live-disable proof", detail_table("Live Disable Proof", cert.get("live_disable_proof", {})))
        + _evidence_panel("mc-cert-final", "Show final certification evidence", detail_table("Mission Control Final Certification", {
            "version": final.get("version"),
            "overall": final.get("overall"),
            "blockers": final.get("blockers"),
            "api_contracts": final.get("api_contracts"),
            "performance": final.get("performance"),
            "resilience": final.get("resilience"),
            "state_hash": final.get("state_hash"),
        }))
        + _evidence_panel("mc-cert-checks", "Show final certification checks", detail_table("Final Certification Checks", final.get("checks", [])))
        + '</div>'
    )
