"""Canonical CSS navigation destinations (Phase 177H).

Centralizes Home / Mission Control / Reports / module paths so templates do not
hard-code hosts, ports, or stale routes. Cross-surface links use optional env
bases; otherwise relative same-origin paths are returned (safe for reverse proxy).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse


@dataclass(frozen=True)
class CanonicalRoutes:
    """Per-surface landing and primary destinations."""

    mobile_home: str = "/mobile-launcher"
    mobile_dashboard: str = "/dashboard"
    mobile_reports: str = "/reports"
    mobile_positions: str = "/positions"
    mobile_trade: str = "/trade"
    mobile_risk: str = "/risk"
    mobile_alerts: str = "/alerts"
    mobile_broker: str = "/broker"
    mobile_execution: str = "/trade-status"
    mobile_runtime: str = "/session-command-centre"
    mobile_certification: str = "/live-readiness-certification"
    mobile_controls: str = "/controls"
    mobile_users: str = "/users"
    mobile_audit: str = "/audit"
    mobile_history: str = "/history"
    mobile_governance: str = "/governance"
    mobile_opportunities: str = "/opportunities"
    mobile_market: str = "/market"
    mobile_margin: str = "/margin"
    mobile_micro_pilot: str = "/live-micro-pilot"
    mobile_trade_summary: str = "/trade-summary"
    mc_root: str = "/mission-control"
    mc_home: str = "/mission-control/executive-overview"
    mc_reports: str = "/mission-control/reports"
    mc_options_income: str = "/mission-control/options-income"
    mc_broker: str = "/mission-control/broker-management"
    mc_runtime: str = "/mission-control/runtime-operations"
    mc_portfolio: str = "/mission-control/portfolio"
    mc_trade: str = "/mission-control/trade-operations"
    mc_risk: str = "/mission-control/risk-command"
    mc_alerts: str = "/mission-control/alerts-incidents"
    report_viewer: str = "/reports/viewer"
    mc_report_viewer: str = "/mission-control/reports/viewer"


ROUTES = CanonicalRoutes()

# Allowed path prefixes for cross-surface link construction (no open redirects).
_ALLOWED_PATH_PREFIXES = (
    "/",
    "/dashboard",
    "/reports",
    "/mission-control",
    "/mobile",
    "/api/",
)


def _env_base(name: str) -> str:
    return (os.environ.get(name) or "").strip().rstrip("/")


def _safe_join(base: str, path: str) -> str:
    """Join base + path; reject absolute external redirects not in base host."""
    path = path if path.startswith("/") else f"/{path}"
    if not any(path == p or path.startswith(p if p.endswith("/") else f"{p}/") or path.startswith(p) for p in _ALLOWED_PATH_PREFIXES):
        # Still allow known absolute paths under /
        if not path.startswith("/"):
            return ROUTES.mobile_home
    if not base:
        return path
    parsed = urlparse(base)
    if parsed.scheme and parsed.netloc:
        # Only allow http(s) bases from configuration — never user-supplied.
        if parsed.scheme not in {"http", "https"}:
            return path
        return urljoin(base + "/", path.lstrip("/"))
    return path


def mobile_home_href(*, for_surface: str = "mobile") -> str:
    """Primary CSS basic mobile launcher landing.

    Mobile-dashboard surfaces may use the configured launcher origin. Launcher
    and Mission Control surfaces use the same-origin rendered landing route.
    """
    if for_surface in {"mobile", "dashboard"}:
        base = _env_base("CSS_LAUNCHER_PUBLIC_URL") or _env_base(
            "CSS_MISSION_CONTROL_BASE_URL"
        )
        return _safe_join(base, ROUTES.mobile_home)
    return ROUTES.mobile_home


def mission_control_home_href(*, for_surface: str = "mobile") -> str:
    """Mission Control executive overview (canonical MC landing)."""
    if for_surface == "mobile":
        base = _env_base("CSS_MISSION_CONTROL_BASE_URL") or _env_base("CSS_LAUNCHER_PUBLIC_URL")
        return _safe_join(base, ROUTES.mc_home)
    return ROUTES.mc_home


def cross_surface_href(path: str, *, target: str = "mission_control") -> str:
    """Build a path toward another CSS surface without open redirects."""
    path = path if str(path).startswith("/") else f"/{path}"
    if target in {"mission_control", "launcher", "mc"}:
        base = _env_base("CSS_MISSION_CONTROL_BASE_URL") or _env_base("CSS_LAUNCHER_PUBLIC_URL")
        return _safe_join(base, path)
    if target in {"mobile", "dashboard"}:
        base = _env_base("CSS_MOBILE_DASHBOARD_BASE_URL") or _env_base("CSS_MOBILE_PUBLIC_URL")
        return _safe_join(base, path)
    return path


def breadcrumbs_for(trail: list[tuple[str, str | None]]) -> list[dict[str, Any]]:
    """Build breadcrumb items: (label, href|None). Current page has href=None."""
    items: list[dict[str, Any]] = []
    for i, (label, href) in enumerate(trail):
        is_current = i == len(trail) - 1 or href is None
        items.append(
            {
                "label": str(label),
                "href": None if is_current else href,
                "current": is_current,
            }
        )
    if items:
        items[-1]["current"] = True
        items[-1]["href"] = None
    return items


__all__ = [
    "CanonicalRoutes",
    "ROUTES",
    "breadcrumbs_for",
    "cross_surface_href",
    "mobile_home_href",
    "mission_control_home_href",
]
