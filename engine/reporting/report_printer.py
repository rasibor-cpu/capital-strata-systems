"""
engine/reporting/report_printer.py

Central Report Registry (FinCon Grade – Phase Expanded)
--------------------------------------------------------
• Authority gated
• Extensible registry
• Integrity compatible
• Supports:
    - timeframe
    - as_of_date
    - sections
    - filters
• Designed for regulator reproducibility
"""

from __future__ import annotations

from typing import Dict, Any, Callable, List, Optional
from datetime import datetime
import json
from pathlib import Path

# Existing ageing support
from engine.reporting.ageing_reports import (
    compute_ageing,
    format_ageing_report,
)

# New approval queue snapshot
from engine.reporting.approval_queue_snapshot import (
    build_approval_queue_snapshot,
)

# ============================================================
# Registry
# ============================================================

_REPORT_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_report(
    name: str,
    handler: Callable[..., str],
    roles: List[str],
    default_sections: Optional[List[str]] = None,
) -> None:
    _REPORT_REGISTRY[name] = {
        "handler": handler,
        "roles": roles,
        "default_sections": default_sections or [],
    }


def list_reports() -> Dict[str, Any]:
    return {
        name: {
            "roles": meta["roles"],
            "default_sections": meta["default_sections"],
        }
        for name, meta in _REPORT_REGISTRY.items()
    }


# ============================================================
# Authority Check
# ============================================================

def _check_role(name: str, role: str) -> None:
    meta = _REPORT_REGISTRY.get(name)
    if not meta:
        raise ValueError(f"Unknown report '{name}'")

    if role not in meta["roles"]:
        raise PermissionError(
            f"Insufficient authority to print '{name}'. "
            f"Requires one of {meta['roles']}"
        )


# ============================================================
# Report Engine
# ============================================================

def print_report(
    report_name: str,
    role: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
    sections: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> str:

    filters = filters or {}
    sections = sections or []

    _check_role(report_name, role)

    handler = _REPORT_REGISTRY[report_name]["handler"]

    content = handler(
        from_date=from_date,
        to_date=to_date,
        as_of_date=as_of_date,
        sections=sections,
        filters=filters,
    )

    footer = (
        "\n\n"
        "Sign-off:\n"
        f"  Printed by : {role}\n"
        f"  Generated  : {datetime.utcnow().isoformat()}Z\n"
    )

    return content + footer


# ============================================================
# AGEING HANDLERS
# ============================================================

def _ar_ageing_handler(**kwargs) -> str:
    as_of = kwargs.get("as_of_date")
    filters = kwargs.get("filters") or {}

    if as_of:
        from datetime import datetime
        as_of_dt = datetime.strptime(as_of, "%Y-%m-%d").date()
    else:
        as_of_dt = datetime.utcnow().date()

    data = compute_ageing(filters, as_of_dt)
    return format_ageing_report("AR AGEING REPORT", data)


def _ap_ageing_handler(**kwargs) -> str:
    return _ar_ageing_handler(**kwargs)


def _gl_ageing_handler(**kwargs) -> str:
    return _ar_ageing_handler(**kwargs)


# ============================================================
# GOVERNANCE SUMMARY
# ============================================================

def _governance_summary_handler(**kwargs) -> str:
    path = Path("audit_logs") / "governance_decisions.jsonl"
    if not path.exists():
        return "No governance log found."

    allow = 0
    block = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                if obj.get("decision") == "ALLOW":
                    allow += 1
                elif obj.get("decision") == "BLOCK":
                    block += 1
            except Exception:
                continue

    return (
        "=== GOVERNANCE ANALYSIS SUMMARY ===\n"
        f"ALLOW : {allow}\n"
        f"BLOCK : {block}\n"
    )


# ============================================================
# APPROVAL QUEUE SNAPSHOT
# ============================================================

def _approval_queue_snapshot_handler(**kwargs) -> str:
    return build_approval_queue_snapshot(**kwargs)


# ============================================================
# REGISTER REPORTS
# ============================================================

COMMON_ROLES = ["ADMIN", "SUPER_USER", "FINCON_REPORTING"]

register_report("ar_ageing", _ar_ageing_handler, COMMON_ROLES)
register_report("ap_ageing", _ap_ageing_handler, COMMON_ROLES)
register_report("gl_ageing", _gl_ageing_handler, COMMON_ROLES)

register_report("governance_summary", _governance_summary_handler, COMMON_ROLES)

register_report(
    "approval_queue_snapshot",
    _approval_queue_snapshot_handler,
    COMMON_ROLES,
    default_sections=["pending_by_maker"],
)