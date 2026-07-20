"""Phase 177H — shared enterprise navigation shell and route helpers."""

from dashboard.enterprise_shell.nav_contract import (
    build_enterprise_navigation_contract,
    match_active_destination,
)
from dashboard.enterprise_shell.reports_hub import build_reports_hub_payload
from dashboard.enterprise_shell.routes import (
    CanonicalRoutes,
    breadcrumbs_for,
    cross_surface_href,
    mobile_home_href,
    mission_control_home_href,
)
from dashboard.enterprise_shell.shell import (
    render_breadcrumbs,
    render_brand_home_link,
    render_mobile_enterprise_nav,
    render_mobile_footer_nav,
    shell_status_indicators,
)

__all__ = [
    "CanonicalRoutes",
    "breadcrumbs_for",
    "build_enterprise_navigation_contract",
    "build_reports_hub_payload",
    "cross_surface_href",
    "match_active_destination",
    "mobile_home_href",
    "mission_control_home_href",
    "render_brand_home_link",
    "render_breadcrumbs",
    "render_mobile_enterprise_nav",
    "render_mobile_footer_nav",
    "shell_status_indicators",
]
