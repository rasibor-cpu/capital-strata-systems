"""
Phase 177F — Options Income surface linkage helper.

Does not remount OI APIs on mobile. Provides canonical detail URL construction.
"""

from __future__ import annotations

import os
from typing import Any


def options_income_detail_link() -> dict[str, Any]:
    """
    Build Options Income detail navigation metadata.

    Prefer CSS_MISSION_CONTROL_BASE_URL / CSS_LAUNCHER_PUBLIC_URL when set.
    Otherwise return a same-path relative route (works when MC is on the same host,
    or when a reverse-proxy maps /mission-control).
    """
    base = (
        os.environ.get("CSS_MISSION_CONTROL_BASE_URL")
        or os.environ.get("CSS_LAUNCHER_PUBLIC_URL")
        or ""
    ).strip().rstrip("/")
    path = "/mission-control/options-income"
    href = f"{base}{path}" if base else path
    return {
        "path": path,
        "href": href,
        "label": "Options Income",
        "advisory_only": True,
        "execution_blocked": True,
        "same_origin_api_expected": False,
        "detail_host": "MISSION_CONTROL_LAUNCHER",
        "note": (
            "Full Options Income APIs and Mission Control page are served by the "
            "canonical launcher (:8765). Mobile exposes a summary card and deep link only."
        ),
        "source": "OPTIONS_INCOME_RUNTIME|CONFIGURATION",
        "provenance": "OPTIONS_INCOME_RUNTIME",
    }


__all__ = ["options_income_detail_link"]
