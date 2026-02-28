"""
backend/app/reporting_api.py

Global Reporting Gateway (FinCon Grade)
---------------------------------------
Authority-gated reporting layer with:
- Schema registry enforcement (fail-closed)
- Integrity hashing (auditor reproducibility)
- Central report registry dispatch via engine.reporting.report_printer

This is the canonical API used by report_center.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

from engine.reporting.report_printer import print_report, list_reports
from engine.reporting.report_integrity import attach_integrity_metadata
from engine.reporting.schema_registry import get_schema_version


# ============================================================
# Authority Model
# ============================================================

ALLOWED_ROLES = {"ADMIN", "SUPER_USER", "FINCON_REPORTING"}


def _check_authority(user_role: str) -> None:
    role = (user_role or "").strip().upper()
    if role not in ALLOWED_ROLES:
        raise PermissionError(
            f"Insufficient authority for reporting. Requires one of: {sorted(ALLOWED_ROLES)}"
        )


# ============================================================
# Report Request Object
# ============================================================

@dataclass
class GlobalReportRequest:
    report_name: str
    role: str
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    as_of_date: Optional[str] = None
    sections: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Public API
# ============================================================

def list_available_reports(user_role: str) -> Dict[str, Any]:
    _check_authority(user_role)

    schema_name = "list_available_reports"
    schema_version = get_schema_version(schema_name)  # fail-closed if missing

    payload = {
        "available_reports": list_reports(),
        "role": (user_role or "").strip().upper(),
        "generated_at": datetime.utcnow().isoformat(),
    }

    return attach_integrity_metadata(
        payload,
        schema_name=schema_name,
        schema_version=schema_version,
    )


def generate_report(req: GlobalReportRequest) -> Dict[str, Any]:
    _check_authority(req.role)

    report_name = (req.report_name or "").strip()
    if not report_name:
        raise ValueError("report_name is required")

    # Enforce schema registry (fail-closed)
    schema_version = get_schema_version(report_name)

    result = print_report(
        report_name=report_name,
        role=(req.role or "").strip().upper(),
        from_date=req.from_date,
        to_date=req.to_date,
        as_of_date=req.as_of_date,
        sections=req.sections,
        filters=req.filters,
    )

    payload = {
        "report_name": report_name,
        "schema_version": schema_version,
        "generated_at": datetime.utcnow().isoformat(),
        "role": (req.role or "").strip().upper(),
        "content": result,
    }

    return attach_integrity_metadata(
        payload,
        schema_name=report_name,
        schema_version=schema_version,
    )