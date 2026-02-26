"""
backend/app/reporting_api.py

Global Reporting Gateway
------------------------
• Can be called from ANY screen
• Authority-gated (ADMIN / SUPER_USER / FINCON_REPORTING)
• Supports:
    - list available reports
    - print report with timeframe
    - explicit sections
    - arbitrary filter payload
• Designed for auditor / regulator reproducibility
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from engine.reporting.report_printer import print_report, list_reports


# ============================================================
# Authority Model
# ============================================================

ALLOWED_ROLES = {"ADMIN", "SUPER_USER", "FINCON_REPORTING"}


def _check_authority(user_role: str) -> None:
    if user_role not in ALLOWED_ROLES:
        raise PermissionError(
            f"Insufficient authority for reporting. "
            f"Requires one of: {sorted(ALLOWED_ROLES)}"
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
    return {
        "available_reports": list_reports(),
        "role": user_role,
        "timestamp": datetime.utcnow().isoformat(),
    }


def generate_report(req: GlobalReportRequest) -> Dict[str, Any]:
    _check_authority(req.role)

    result = print_report(
        report_name=req.report_name,
        role=req.role,
        from_date=req.from_date,
        to_date=req.to_date,
        as_of_date=req.as_of_date,
        sections=req.sections,
        filters=req.filters,
    )

    return {
        "report_name": req.report_name,
        "generated_at": datetime.utcnow().isoformat(),
        "role": req.role,
        "content": result,
    }