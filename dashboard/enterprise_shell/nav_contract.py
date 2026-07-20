"""Canonical enterprise navigation contract (Phase 177H.1).

Server-side source of truth serialized for Mission Control, mobile dashboard,
and the launcher SPA. Clients must not invent destinations or redirect targets.
"""

from __future__ import annotations

from typing import Any, Mapping

from dashboard.enterprise_shell.routes import (
    ROUTES,
    cross_surface_href,
    mobile_home_href,
    mission_control_home_href,
)
from dashboard.enterprise_shell.shell import shell_status_indicators

SCHEMA_VERSION = "css.enterprise_navigation.v1"
SPA_SHELL_CACHE = "css-launcher-spa-shell-v177h1"


def _dest(
    *,
    id: str,
    label: str,
    href: str | None = None,
    spa_screen: str | None = None,
    icon: str = "",
    category: str = "primary",
    primary: bool = False,
    more: bool = False,
    enabled: bool = True,
    coming_soon: bool = False,
    cross_surface: bool = False,
    match: list[str] | None = None,
    aria_label: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    return {
        "id": id,
        "label": label,
        "icon": icon,
        "href": href,
        "spa_screen": spa_screen,
        "category": category,
        "primary": primary,
        "more": more,
        "enabled": enabled and not coming_soon,
        "coming_soon": coming_soon,
        "cross_surface": cross_surface,
        "match": match or ([spa_screen] if spa_screen else ([href] if href else [])),
        "aria_label": aria_label or label,
        "note": note,
        "external_indicator": cross_surface,
    }


def build_enterprise_navigation_contract(
    *,
    surface: str = "launcher_spa",
    platform_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build read-only navigation contract from canonical route helpers."""
    home = mobile_home_href(
        for_surface="mission_control" if surface in {"launcher_spa", "mission_control", "launcher"} else "mobile"
    )
    mc = mission_control_home_href(
        for_surface="mobile" if surface == "mobile" else "mission_control"
    )
    # On launcher SPA, Mission Control / Reports are same-origin relative paths.
    if surface in {"launcher_spa", "mission_control", "launcher"}:
        mc = ROUTES.mc_home
        reports = ROUTES.mc_reports
        oi = ROUTES.mc_options_income
        broker = ROUTES.mc_broker
        runtime_mc = ROUTES.mc_runtime
        oi_viewer = "/api/options-income/report.viewer"
        discovery = "/api/reports"
    else:
        reports = cross_surface_href(ROUTES.mc_reports, target="mission_control")
        oi = cross_surface_href(ROUTES.mc_options_income, target="mission_control")
        broker = cross_surface_href(ROUTES.mc_broker, target="mission_control")
        runtime_mc = cross_surface_href(ROUTES.mc_runtime, target="mission_control")
        oi_viewer = cross_surface_href("/api/options-income/report.viewer", target="mission_control")
        discovery = cross_surface_href("/api/reports", target="mission_control")

    primary = [
        _dest(
            id="home",
            label="Home",
            href=home,
            icon="home",
            primary=True,
            cross_surface=surface in {"launcher_spa", "mission_control", "launcher"},
            match=["/dashboard", home],
            aria_label="CSS Home — Mobile Dashboard landing",
            note="Canonical CSS Mobile Dashboard landing; not browser Back.",
        ),
        _dest(
            id="mission_control",
            label="Mission Control",
            href=mc,
            icon="grid",
            primary=True,
            match=[ROUTES.mc_home, ROUTES.mc_root, "/mission-control"],
            aria_label="Mission Control executive overview",
        ),
        _dest(
            id="trade",
            label="Trade",
            spa_screen="trade" if surface == "launcher_spa" else None,
            href=None if surface == "launcher_spa" else ROUTES.mobile_trade,
            icon="trade",
            primary=True,
            match=["trade", "/trade", "/mobile#trade"],
            note="Navigates to trade surfaces only. Execution remains blocked unless authority is granted elsewhere.",
        ),
        _dest(
            id="reports",
            label="Reports",
            href=reports,
            icon="file",
            primary=True,
            match=[ROUTES.mc_reports, ROUTES.mobile_reports, "/api/reports"],
            aria_label="Canonical Reports hub",
        ),
        _dest(
            id="more",
            label="More",
            spa_screen="more",
            icon="more",
            primary=True,
            match=["more"],
            aria_label="More modules menu",
        ),
    ]

    more = [
        _dest(id="positions", label="Positions", spa_screen="positions", icon="positions", more=True, match=["positions"]),
        _dest(id="execution", label="Execution", spa_screen="execution", icon="execution", more=True, match=["execution"]),
        _dest(id="risk", label="Risk", spa_screen="risk", icon="risk", more=True, match=["risk"]),
        _dest(id="alerts", label="Alerts", spa_screen="alerts", icon="alerts", more=True, match=["alerts"]),
        _dest(
            id="spa_runtime",
            label="Runtime (Mobile SPA)",
            spa_screen="home",
            icon="activity",
            more=True,
            match=["home"],
            note="Launcher SPA runtime panels (local). Canonical Home remains the Mobile Dashboard landing.",
        ),
        _dest(
            id="broker_management",
            label="Broker Management",
            href=broker,
            icon="plug",
            more=True,
            cross_surface=surface == "mobile",
            match=[ROUTES.mc_broker],
        ),
        _dest(
            id="runtime_diagnostics",
            label="Runtime Diagnostics",
            href=runtime_mc,
            icon="activity",
            more=True,
            cross_surface=surface == "mobile",
            match=[ROUTES.mc_runtime],
        ),
        _dest(
            id="options_income",
            label="Options Income",
            href=oi,
            icon="layers",
            more=True,
            cross_surface=surface == "mobile",
            match=[ROUTES.mc_options_income],
        ),
        _dest(
            id="options_income_report",
            label="Options Income Report",
            href=oi_viewer,
            icon="file",
            more=True,
            match=["/api/options-income/report.viewer", "/api/reports/options_income_executive/view"],
            note="Opens Phase 177H paginated viewer (one page at a time).",
        ),
        _dest(
            id="report_discovery",
            label="Report Discovery API",
            href=discovery,
            icon="file",
            more=True,
            match=["/api/reports"],
        ),
        _dest(
            id="certification",
            label="Certification",
            href=ROUTES.mc_home.replace("executive-overview", "certification-readiness")
            if surface != "mobile"
            else cross_surface_href("/mission-control/certification-readiness", target="mission_control"),
            icon="badge",
            more=True,
            match=["/mission-control/certification-readiness"],
        ),
        _dest(
            id="settings",
            label="Settings",
            href="/mission-control/system-configuration"
            if surface != "mobile"
            else cross_surface_href("/mission-control/system-configuration", target="mission_control"),
            icon="sliders",
            more=True,
            match=["/mission-control/system-configuration"],
        ),
        _dest(
            id="administration",
            label="Administration",
            href="/mission-control/users-governance"
            if surface != "mobile"
            else cross_surface_href("/mission-control/users-governance", target="mission_control"),
            icon="users",
            more=True,
            match=["/mission-control/users-governance"],
        ),
    ]

    # Safety: never expose IBKR
    destinations = primary + more
    for d in destinations:
        blob = f"{d.get('href') or ''} {d.get('label') or ''} {d.get('id') or ''}".lower()
        if "ibkr" in blob or "interactive brokers" in blob:
            d["enabled"] = False
            d["coming_soon"] = True
            d["href"] = None
            d["note"] = "IBKR is roadmap-excluded from Tier-1."

    status = shell_status_indicators(platform_status)
    crumbs = {
        "home": [("Home", home), ("Mobile", None)],
        "trade": [("Home", home), ("Mobile", "/mobile"), ("Trade", None)],
        "positions": [("Home", home), ("Mobile", "/mobile"), ("Positions", None)],
        "execution": [("Home", home), ("Mobile", "/mobile"), ("Execution", None)],
        "risk": [("Home", home), ("Mobile", "/mobile"), ("Risk", None)],
        "alerts": [("Home", home), ("Mobile", "/mobile"), ("Alerts", None)],
        "reports": [("Home", home), ("Reports", None)],
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "surface": surface,
        "canonical_home": home,
        "spa_entry": "/mobile",
        "pwa_start_url": "/mobile-launcher",
        "pwa_start_note": (
            "Installed PWA opens the launcher landing (/mobile-launcher), not Mission Control. "
            "From there operators open /mobile (SPA) or Mission Control via canonical links. "
            "SPA hash restore may reopen the last local screen but Home always returns to the Mobile Dashboard landing."
        ),
        "shell_cache": SPA_SHELL_CACHE,
        "write_routes": False,
        "execution_allowed": False,
        "advisory_only": True,
        "platform_status": status,
        "primary": primary,
        "more": more,
        "destinations": destinations,
        "breadcrumbs": crumbs,
        "spa_screens": ["home", "positions", "execution", "trade", "risk", "alerts"],
        "active_match_rules": {
            "normalize": "exact_path_or_exact_spa_screen",
            "forbid_broad_substring": True,
            "notes": "Match destination.match entries exactly after stripping query; spa_screen matches location.hash without #.",
        },
        "reports": {
            "hub_href": reports,
            "discovery_href": discovery,
            "options_income_viewer_href": oi_viewer,
            "default_viewer": "paginated",
            "continuous_scroll_default": False,
        },
    }


def match_active_destination(contract: Mapping[str, Any], *, path: str = "", spa_screen: str = "") -> str | None:
    """Return destination id for exact route/screen match (no broad substring)."""
    path_n = str(path or "").split("?", 1)[0].rstrip("/") or "/"
    screen_n = str(spa_screen or "").strip().lstrip("#").lower()
    for dest in contract.get("destinations") or []:
        if not dest.get("enabled", True):
            continue
        for candidate in dest.get("match") or []:
            c = str(candidate or "").strip()
            if not c:
                continue
            if c.startswith("/"):
                if path_n == c.rstrip("/") or path_n == c:
                    return str(dest["id"])
            elif screen_n and c.lower() == screen_n:
                return str(dest["id"])
    return None


__all__ = [
    "SCHEMA_VERSION",
    "SPA_SHELL_CACHE",
    "build_enterprise_navigation_contract",
    "match_active_destination",
]
