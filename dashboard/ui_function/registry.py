"""Assemble and validate the Phase 176C UI function registry."""

from __future__ import annotations

from collections import Counter
from typing import Any

from dashboard.ui_function.models import CSSUIFunctionDefinition
from dashboard.ui_function.registry_mc import MC_CONTROLS
from dashboard.ui_function.registry_mobile import MOBILE_CONTROLS
from dashboard.ui_function.registry_web import WEB_CONTROLS


def all_controls() -> tuple[CSSUIFunctionDefinition, ...]:
    return tuple(MC_CONTROLS + WEB_CONTROLS + MOBILE_CONTROLS)


def registry_summary() -> dict[str, Any]:
    controls = all_controls()
    by_status = Counter(c.implementation_status for c in controls)
    pages = {c.page_id for c in controls}
    subtabs = [c for c in controls if c.control_type == "subtab"]
    broken = [c for c in controls if c.implementation_status == "BROKEN"]
    unverified = [c for c in controls if c.implementation_status == "UNVERIFIED"]
    return {
        "total_controls": len(controls),
        "pages_audited": len(pages),
        "subtabs_audited": len(subtabs),
        "by_status": dict(by_status),
        "broken_ids": [c.control_id for c in broken],
        "unverified_ids": [c.control_id for c in unverified],
        "control_ids": [c.control_id for c in controls],
    }


def control_to_route_matrix() -> list[dict[str, str]]:
    rows = []
    for c in all_controls():
        rows.append(
            {
                "control_id": c.control_id,
                "page_id": c.page_id,
                "label": c.label,
                "desktop_route": c.desktop_route,
                "mobile_route": c.mobile_route,
                "expected_api": c.expected_api,
                "expected_service": c.expected_service,
                "status": c.implementation_status,
                "desktop_mobile": c.desktop_mobile,
            }
        )
    return rows


def assert_registry_complete() -> None:
    summary = registry_summary()
    if summary["unverified_ids"]:
        raise AssertionError(f"UNVERIFIED controls remain: {summary['unverified_ids']}")
    if summary["broken_ids"]:
        raise AssertionError(f"BROKEN controls remain: {summary['broken_ids']}")
    ids = summary["control_ids"]
    if len(ids) != len(set(ids)):
        dupes = [i for i, n in Counter(ids).items() if n > 1]
        raise AssertionError(f"Duplicate control_ids: {dupes}")


__all__ = [
    "all_controls",
    "assert_registry_complete",
    "control_to_route_matrix",
    "registry_summary",
]
