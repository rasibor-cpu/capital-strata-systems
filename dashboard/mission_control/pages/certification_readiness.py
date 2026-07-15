from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels, warning_banner


def render(state: dict) -> str:
    cert = section(state, "certification")
    summary = section(state, "governance_summary_console")
    final = section(state, "final_certification")
    return (
        page_header("Certification and Readiness", "Read-only RC1, operational, Options Income, broker, runtime, live-disable proof, blockers, and prerequisites.")
        + warning_banner("READY_FOR_CONTROLLED_RC1_RUNTIME is not READY_FOR_LIVE_TRADING.", status="warn")
        + metric_grid(
            (
                ("RC1 Platform", cert.get("rc1_platform_certification"), cert.get("rc1_platform_certification")),
                ("RC1 Operational", cert.get("rc1_operational_readiness"), cert.get("rc1_operational_readiness")),
                ("Options Income", cert.get("options_income_certification"), cert.get("options_income_certification")),
                ("Broker Readiness", cert.get("broker_readiness"), cert.get("broker_readiness")),
                ("Runtime Readiness", cert.get("runtime_readiness"), cert.get("runtime_readiness")),
                ("Live Trading", cert.get("ready_for_live_trading"), cert.get("ready_for_live_trading")),
            )
        )
        + split_panels(
            detail_table("Live Disable Proof", cert.get("live_disable_proof", {})),
            detail_table("Blockers And Warnings", {
                "blockers": cert.get("blockers"),
                "warnings": cert.get("warnings"),
                "ready_for_controlled_rc1_runtime": cert.get("ready_for_controlled_rc1_runtime"),
                "ready_for_live_trading": cert.get("ready_for_live_trading"),
            }),
            detail_table("Governance Summary", {
                "security_posture": summary.get("security_posture"),
                "audit_posture": summary.get("audit_posture"),
                "approval_posture": summary.get("approval_posture"),
                "configuration_posture": summary.get("configuration_posture"),
                "certification_posture": summary.get("certification_posture"),
                "write_routes_enabled": summary.get("write_routes_enabled"),
                "operator_actions_enabled": summary.get("operator_actions_enabled"),
            }),
            detail_table("Mission Control Final Certification", {
                "version": final.get("version"),
                "overall": final.get("overall"),
                "blockers": final.get("blockers"),
                "api_contracts": final.get("api_contracts"),
                "performance": final.get("performance"),
                "resilience": final.get("resilience"),
                "state_hash": final.get("state_hash"),
            }),
            detail_table("Final Certification Checks", final.get("checks", [])),
        )
    )
