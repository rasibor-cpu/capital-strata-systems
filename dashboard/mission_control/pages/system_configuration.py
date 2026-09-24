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


def _control_state(value: object) -> str:
    return "ENABLED" if value is True else "DISABLED" if value is False else "UNAVAILABLE"


def _planning_state(value: object) -> str:
    return "PLANNING_ONLY" if value is True else "NOT_PLANNING_ONLY" if value is False else "UNAVAILABLE"


def render(state: dict) -> str:
    config = section(state, "configuration")
    console = section(state, "configuration_console")
    flags = section(state, "feature_flags_console")
    history = section(state, "change_history_console")
    rollback = section(state, "rollback_console")
    return (
        page_header("System Configuration", "Safe non-secret runtime, engine, broker, order-limit, feature flag, endpoint, and refresh summaries.")
        + warning_banner("Live limits and credentials cannot be edited through Mission Control MC-001.", status="bad")
        + '<nav class="mc-page-jump" aria-label="System Configuration sections">'
          '<a href="#mc-config-runtime">Runtime</a>'
          '<a href="#mc-config-controls">Controls</a>'
          '<a href="#mc-config-rollback">Rollback</a>'
          '<a href="#mc-config-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Runtime Mode", config.get("runtime_mode"), config.get("runtime_mode")),
                ("Engine Mode", config.get("engine_mode"), config.get("engine_mode")),
                ("Selected Broker", config.get("selected_broker"), "neutral"),
                ("Editing", _control_state(console.get("editing_enabled")), _control_state(console.get("editing_enabled"))),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-config-priority",
            aria_label="System Configuration priority",
        )
        + metric_grid(
            (
                ("Cycle Mode", config.get("cycle_mode"), config.get("cycle_mode")),
                ("Environment", console.get("environment_classification"), console.get("environment_classification")),
                ("Rollback Perform", _control_state(rollback.get("perform_available")), _control_state(rollback.get("perform_available"))),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="System Configuration secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-config-runtime", detail_table("Runtime Configuration Snapshot", {
            "runtime_mode": config.get("runtime_mode"),
            "engine_mode": config.get("engine_mode"),
            "cycle_mode": config.get("cycle_mode"),
            "selected_broker": config.get("selected_broker"),
            "environment_classification": console.get("environment_classification"),
        }))
        + _anchor_panel("mc-config-controls", detail_table("Control Posture", {
            "configuration_editing": _control_state(console.get("editing_enabled")),
            "feature_flag_editing": _control_state(flags.get("editing_enabled")),
            "live_limit_editing": "DISABLED",
        }))
        + _anchor_panel("mc-config-rollback", detail_table("Rollback Snapshot", {
            "planning_posture": _planning_state(rollback.get("planning_only")),
            "perform_available": _control_state(rollback.get("perform_available")),
            "eligible_target_count": len(rollback.get("eligible_targets", [])) if isinstance(rollback.get("eligible_targets"), list) else 0,
        }))
        + _evidence_panel("mc-config-evidence", "Show limit and feature evidence", detail_table("Limit And Feature Summary", {
            "canonical_order_limit_configuration": config.get("canonical_order_limit_configuration"),
            "paper_limits": config.get("paper_limits"),
            "preview_limits": config.get("preview_limits"),
            "live_pilot_limits": config.get("live_pilot_limits"),
            "live_limit_overrides": config.get("live_limit_overrides"),
            "feature_flags": config.get("feature_flags"),
        }))
        + _evidence_panel("mc-config-services", "Show service and refresh evidence", detail_table("Services", {
            "service_endpoints": config.get("service_endpoints"),
            "data_refresh_settings": config.get("data_refresh_settings"),
        }))
        + _evidence_panel("mc-config-console", "Show configuration-console evidence", detail_table("Configuration Console", {
            "runtime_mode": console.get("runtime_mode"),
            "engine_mode": console.get("engine_mode"),
            "limits": console.get("limits"),
            "versions": console.get("versions"),
            "deployment": console.get("deployment"),
            "environment_classification": console.get("environment_classification"),
            "editing_enabled": console.get("editing_enabled"),
            "state_hash": console.get("state_hash"),
        }))
        + _evidence_panel("mc-config-flags", "Show feature-flag evidence", detail_table("Feature Flags", {
            "flags": flags.get("flags"),
            "summary": flags.get("summary"),
            "editing_enabled": flags.get("editing_enabled"),
        }))
        + _evidence_panel("mc-config-history", "Show change history", detail_table("Change History", history.get("changes", [])))
        + _evidence_panel("mc-config-rollback-evidence", "Show rollback-plan evidence", detail_table("Rollback Planner", {
            "eligible_targets": rollback.get("eligible_targets"),
            "planning_only": rollback.get("planning_only"),
            "perform_available": rollback.get("perform_available"),
        }))
        + '</div>'
    )
