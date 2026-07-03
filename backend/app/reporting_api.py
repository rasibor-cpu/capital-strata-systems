"""
Global Reporting Gateway – Phase 17 Hardened
Capital Strata Systems

Authority-gated reporting layer with:
- Schema versioning
- Integrity hashing
- Auditor reproducibility
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from engine.reporting.report_printer import print_report, list_reports
from engine.reporting.report_integrity import attach_integrity_metadata


# ============================================================
# Authority Model
# ============================================================

ALLOWED_ROLES = {"ADMIN", "SUPER_USER", "FINCON_REPORTING"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


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

    payload = {
        "available_reports": list_reports(),
        "role": user_role,
        "generated_at": _now_iso(),
    }

    return attach_integrity_metadata(payload)


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

    payload = {
        "report_name": req.report_name,
        "generated_at": _now_iso(),
        "role": req.role,
        "content": result,
    }

    return attach_integrity_metadata(payload)
