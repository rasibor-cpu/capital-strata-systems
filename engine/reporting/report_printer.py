"""
engine/reporting/report_printer.py

Central Report Registry (FinCon Grade)
---------------------------------------
• Authority gated
• Extensible registry
• Supports:
    - timeframe
    - as_of_date
    - explicit sections
    - arbitrary filters
• Designed for regulator reproducibility
"""

from __future__ import annotations

from typing import Dict, Any, Callable, List, Optional
from datetime import datetime
import json
from pathlib import Path

from engine.reporting.ageing_reports import (
    compute_ageing,
    format_ageing_report,
)

# Existing SCP (already registered in your prior step)
from engine.reporting.supervisory_control_pack import generate_scp_report

# NEW: Treasury instrument aggregates
from engine.reporting.treasury_instrument_aggregate import generate_treasury_instrument_aggregate


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
    """
    IMPORTANT GOVERNANCE FEATURE:
    - We automatically inject the caller role into filters so handlers can enforce
      finer-grain logic (department scoping, audit read-only, etc.)
    - Callers may also pass filters["user_id"] for dept resolution.
    """

    filters = filters or {}
    sections = sections or []

    # Gate at registry-level first
    _check_role(report_name, role)

    # Auto-inject caller role into handler context (do not allow spoofing)
    # If caller already passed role inside filters, we overwrite with authoritative role.
    filters["role"] = role

    handler = _REPORT_REGISTRY[report_name]["handler"]

    content = handler(
        from_date=from_date,
        to_date=to_date,
        as_of_date=as_of_date,
        sections=sections,
        filters=filters,
    )

    # Standardized sign-off block
    footer = (
        "\n\n"
        "Sign-off:\n"
        f"  Printed by : {role}\n"
        f"  Generated  : {datetime.utcnow().isoformat()}Z\n"
    )

    return content + footer


# ============================================================
# AGEING REPORT HANDLERS
# ============================================================

def _ar_ageing_handler(**kwargs) -> str:
    as_of = kwargs.get("as_of_date")
    filters = kwargs.get("filters") or {}

    from datetime import datetime
    if as_of:
        as_of_dt = datetime.strptime(as_of, "%Y-%m-%d").date()
    else:
        as_of_dt = datetime.utcnow().date()

    data = compute_ageing(filters, as_of_dt)
    return format_ageing_report("AR AGEING REPORT", data)


def _ap_ageing_handler(**kwargs) -> str:
    as_of = kwargs.get("as_of_date")
    filters = kwargs.get("filters") or {}

    from datetime import datetime
    if as_of:
        as_of_dt = datetime.strptime(as_of, "%Y-%m-%d").date()
    else:
        as_of_dt = datetime.utcnow().date()

    data = compute_ageing(filters, as_of_dt)
    return format_ageing_report("AP AGEING REPORT", data)


def _gl_ageing_handler(**kwargs) -> str:
    as_of = kwargs.get("as_of_date")
    filters = kwargs.get("filters") or {}

    from datetime import datetime
    if as_of:
        as_of_dt = datetime.strptime(as_of, "%Y-%m-%d").date()
    else:
        as_of_dt = datetime.utcnow().date()

    data = compute_ageing(filters, as_of_dt)
    return format_ageing_report("GL AGEING REPORT", data)


# ============================================================
# GOVERNANCE SUMMARY (existing logic stub retained)
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
# SUPERVISORY CONTROL PACK (SCP)
# ============================================================

def _supervisory_control_pack_handler(**kwargs) -> str:
    """
    Supports filters:
      - date: "YYYY-MM-DD"          (business date)
      - supervisor_id: "checker_2"  (optional)
      - mode: detailed | summary | exception
    """
    return generate_scp_report(**kwargs)


# ============================================================
# TREASURY: INSTRUMENT AGGREGATE
# ============================================================

def _treasury_instrument_aggregate_handler(**kwargs) -> str:
    """
    Supports filters:
      - user_id: required for department scoping (except SUPER_USER/AUDIT_CONTROL)
      - mode: detailed | summary | exception
      - date OR from_date/to_date OR as_of_date
    """
    return generate_treasury_instrument_aggregate(**kwargs)


# ============================================================
# REGISTER REPORTS
# ============================================================

COMMON_ROLES = ["ADMIN", "SUPER_USER", "FINCON_REPORTING"]

# Existing common reports
register_report("ar_ageing", _ar_ageing_handler, COMMON_ROLES)
register_report("ap_ageing", _ap_ageing_handler, COMMON_ROLES)
register_report("gl_ageing", _gl_ageing_handler, COMMON_ROLES)
register_report("governance_summary", _governance_summary_handler, COMMON_ROLES)

# SCP (Daily Controls)
register_report("supervisory_control_pack", _supervisory_control_pack_handler, COMMON_ROLES)

# Treasury instrument aggregate (role-gated)
TREASURY_AGG_ROLES = ["TREASURY", "TREASURY_SUPERVISOR", "SUPER_USER", "ADMIN", "AUDIT_CONTROL"]
register_report("treasury_instrument_aggregate", _treasury_instrument_aggregate_handler, TREASURY_AGG_ROLES)