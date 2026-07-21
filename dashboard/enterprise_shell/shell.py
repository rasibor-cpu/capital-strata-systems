"""Reusable enterprise shell fragments (Phase 177H).

Status indicators consume pre-built platform status — they do not resolve runtime mode.
"""

from __future__ import annotations

import html
from typing import Any, Mapping, Sequence

from backend.common.branding import get_brand_service
from dashboard.enterprise_shell.routes import (
    ROUTES,
    breadcrumbs_for,
    cross_surface_href,
    mobile_home_href,
    mission_control_home_href,
)
from dashboard.ui_interaction import render_disclosure


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def shell_status_indicators(platform_status: Mapping[str, Any] | None = None) -> dict[str, str]:
    """Map canonical platform_status fields to concise shell badges (no new calculation)."""
    ps = dict(platform_status or {})
    return {
        "runtime_mode": str(ps.get("runtime_mode") or "DISABLED"),
        "execution_state": str(ps.get("execution_state") or "BLOCKED"),
        "mobile_access_mode": str(ps.get("mobile_access_mode") or "READ_ONLY"),
        "broker_mode": str(ps.get("broker_mode") or "NONE"),
        "engine_mode": str(ps.get("engine_mode") or "UNKNOWN"),
        "advisory": "ADVISORY_ONLY" if ps.get("fail_closed", True) else "UNKNOWN",
    }


def render_breadcrumbs(
    trail: Sequence[tuple[str, str | None]],
    *,
    aria_label: str = "Breadcrumb",
) -> str:
    items = breadcrumbs_for(list(trail))
    if len(items) <= 1:
        return ""
    parts: list[str] = []
    for item in items:
        label = _esc(item["label"])
        if item.get("current") or not item.get("href"):
            parts.append(f'<span class="css-crumb current" aria-current="page">{label}</span>')
        else:
            parts.append(
                f'<a class="css-crumb" href="{_esc(item["href"])}">{label}</a>'
            )
    sep = '<span class="css-crumb-sep" aria-hidden="true">›</span>'
    return (
        f'<nav class="css-breadcrumbs" aria-label="{_esc(aria_label)}">'
        + sep.join(parts)
        + "</nav>"
    )


def render_brand_home_link(*, for_surface: str = "mobile", title: str = "CSS") -> str:
    brand = get_brand_service()
    href = mobile_home_href(for_surface=for_surface)
    return (
        f'<a class="css-brand-home" href="{_esc(href)}" '
        f'aria-label="CSS Home — return to basic mobile landing">'
        f'<img class="css-brand-mark" src="{_esc(brand.asset_url("logo"))}" '
        f'alt="" aria-hidden="true">'
        f'<span class="css-brand-text">{_esc(title)}</span></a>'
    )


def render_mobile_enterprise_nav(
    user_ctx: Mapping[str, Any],
    active: str,
    *,
    can_view_reports: bool = True,
    can_trade: bool = False,
    can_audit: bool = False,
    can_controls: bool = False,
    can_users: bool = False,
) -> str:
    """Compact primary nav + More disclosure for phones and desktop top bar."""
    home = mobile_home_href(for_surface="mobile")
    mc = mission_control_home_href(for_surface="mobile")
    primary = [
        ("home", "Home", home),
        ("mission-control", "Mission Control", mc),
    ]
    if can_trade:
        primary.append(("trade", "Trade Operations", ROUTES.mobile_trade))
    if can_view_reports:
        primary.append(("reports", "Reports", ROUTES.mobile_reports))
    primary.append(("more", "More", "#css-more-menu"))

    primary_html: list[str] = []
    for key, label, href in primary:
        cur = ' aria-current="page"' if active in {key, "dashboard"} and key == "home" else ""
        if key != "home" and active == key:
            cur = ' aria-current="page"'
        cls = "button-link" if cur else "button-link quiet"
        if key == "more":
            primary_html.append(
                f'<a class="{cls}" href="{_esc(href)}" data-css-more-trigger="1">{_esc(label)}</a>'
            )
        else:
            primary_html.append(
                f'<a class="{cls}" href="{_esc(href)}"{cur}>{_esc(label)}</a>'
            )

    more_items: list[tuple[str, str, str]] = [
        ("positions", "Positions", ROUTES.mobile_positions),
        ("execution", "Execution", ROUTES.mobile_execution),
        ("risk", "Risk Command", ROUTES.mobile_risk),
        ("alerts", "Alerts and Incidents", ROUTES.mobile_alerts),
        ("broker", "Broker Management", ROUTES.mobile_broker),
        ("portfolio", "Portfolio", cross_surface_href(ROUTES.mc_portfolio, target="mission_control")),
        ("session-command-centre", "Runtime Operations", ROUTES.mobile_runtime),
        ("live-readiness-certification", "Certification and Readiness", ROUTES.mobile_certification),
        ("history", "History", ROUTES.mobile_history),
        ("governance", "Governance", ROUTES.mobile_governance),
        ("opportunities", "Opportunities", ROUTES.mobile_opportunities),
        ("market", "Market Intelligence", ROUTES.mobile_market),
        ("margin", "Margin", ROUTES.mobile_margin),
        ("trade-summary", "Trade Summary", ROUTES.mobile_trade_summary),
        ("live-micro-pilot", "Micro-Pilot", ROUTES.mobile_micro_pilot),
        ("options-income", "Options Income", cross_surface_href(ROUTES.mc_options_income, target="mission_control")),
        ("documentation-runbooks", "Documentation and Runbooks", cross_surface_href("/mission-control/documentation-runbooks", target="mission_control")),
    ]
    if can_audit:
        more_items.append(("audit", "Audit and Readiness", ROUTES.mobile_audit))
    if can_controls:
        more_items.append(("controls", "System Configuration", ROUTES.mobile_controls))
    if can_users:
        more_items.append(("users", "Users and Governance", ROUTES.mobile_users))

    more_links = "".join(
        f'<li><a href="{_esc(href)}"{" aria-current=\"page\"" if active == key else ""}>{_esc(label)}</a></li>'
        for key, label, href in more_items
    )
    more_panel = render_disclosure(
        panel_id="css-more-menu",
        title="More modules",
        body_html=f'<ul class="css-more-list" role="list">{more_links}</ul>',
        open_by_default=False,
        anchor_id="css-more-menu",
    )

    logout = (
        '<form method="post" action="/logout" class="css-logout">'
        '<button class="ghost" type="submit">Logout</button></form>'
    )
    return (
        f'<div class="css-enterprise-nav">'
        f'{render_brand_home_link(for_surface="mobile")}'
        f'<nav class="top-actions css-primary-nav" aria-label="Primary CSS navigation">'
        f'{"".join(primary_html)}{logout}</nav>'
        f'<div class="css-more-wrap" id="css-more-menu">{more_panel}</div>'
        f"</div>"
    )


def render_mobile_footer_nav(
    active: str,
    *,
    can_view_reports: bool = True,
    can_trade: bool = False,
) -> str:
    """Phone footer: Home · Mission Control · Trade · Reports · More."""
    home = mobile_home_href(for_surface="mobile")
    mc = mission_control_home_href(for_surface="mobile")
    items = [
        ("home", "Home", home),
        ("mission-control", "Mission Control", mc),
    ]
    if can_trade:
        items.append(("trade", "Trade Operations", ROUTES.mobile_trade))
    else:
        items.append(("positions", "Positions", ROUTES.mobile_positions))
    if can_view_reports:
        items.append(("reports", "Reports", ROUTES.mobile_reports))
    items.append(("more", "More", "#css-more-menu"))

    links = []
    for key, label, href in items:
        is_home_active = key == "home" and active in {"home", "dashboard", ""}
        current = is_home_active or (key != "home" and active == key)
        cur = ' aria-current="page"' if current else ""
        links.append(
            f'<a class="css-footer-item{" active" if current else ""}" href="{_esc(href)}"{cur}>'
            f"<span>{_esc(label)}</span></a>"
        )
    return (
        f'<nav class="css-footer-nav" aria-label="Mobile primary navigation">'
        f'{"".join(links)}</nav>'
    )


__all__ = [
    "render_brand_home_link",
    "render_breadcrumbs",
    "render_mobile_enterprise_nav",
    "render_mobile_footer_nav",
    "shell_status_indicators",
]
