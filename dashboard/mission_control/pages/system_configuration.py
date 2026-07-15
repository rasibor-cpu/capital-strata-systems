from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, page_header, section, split_panels, warning_banner


def render(state: dict) -> str:
    config = section(state, "configuration")
    return (
        page_header("System Configuration", "Safe non-secret runtime, engine, broker, order-limit, feature flag, endpoint, and refresh summaries.")
        + warning_banner("Live limits and credentials cannot be edited through Mission Control MC-001.", status="bad")
        + split_panels(
            detail_table("Runtime Configuration", {
                "runtime_mode": config.get("runtime_mode"),
                "engine_mode": config.get("engine_mode"),
                "cycle_mode": config.get("cycle_mode"),
                "selected_broker": config.get("selected_broker"),
            }),
            detail_table("Limit And Feature Summary", {
                "canonical_order_limit_configuration": config.get("canonical_order_limit_configuration"),
                "paper_limits": config.get("paper_limits"),
                "preview_limits": config.get("preview_limits"),
                "live_pilot_limits": config.get("live_pilot_limits"),
                "live_limit_overrides": config.get("live_limit_overrides"),
                "feature_flags": config.get("feature_flags"),
            }),
            detail_table("Services", {
                "service_endpoints": config.get("service_endpoints"),
                "data_refresh_settings": config.get("data_refresh_settings"),
            }),
        )
    )
