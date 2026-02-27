"""
backend/app/screens/report_center.py

Report Center Screen (Print-From-Anywhere Backbone)
---------------------------------------------------
Modes:
- list    : list reports available for caller role
- print   : generate a report (returns content + integrity)
- signoff : supervisor sign-off (immutable JSONL log) against a freshly generated report

Notes:
- This screen is an orchestrator; it delegates integrity + hashing to reporting_api.
- Fail-closed: if anything errors, we return ok=False with a reason.
"""

from __future__ import annotations

from typing import Dict, Any, Optional


def report_center_handler(payload: Dict[str, Any], user_role: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Args:
      payload:
        - mode: "list" | "print" | "signoff"
        - report_name: required for print/signoff
        - from_date / to_date (optional)
        - as_of_date (optional)
        - sections: list (optional)
        - filters: dict (optional)
        - supervisor_id: required for signoff

      user_role:
        - caller role (e.g., SUPER_USER / FINCON_REPORTING / TREASURY / AUDIT_CONTROL)

      user_id:
        - optional caller id (used for traceability if needed)

    Returns:
      dict with ok + payload
    """
    payload = payload or {}
    mode = str(payload.get("mode", "list")).strip().lower()

    # Lazy imports (keeps screen lightweight + avoids import cycles)
    from backend.app.reporting_api import list_available_reports, generate_report, GlobalReportRequest

    # --------------------------
    # LIST REPORTS
    # --------------------------
    if mode == "list":
        try:
            out = list_available_reports(user_role)
            out["ok"] = True
            out["screen"] = "report_center"
            out["user"] = user_id or "(unknown)"
            return out
        except Exception as e:
            return {"ok": False, "screen": "report_center", "error": str(e)}

    # --------------------------
    # PRINT REPORT
    # --------------------------
    if mode == "print":
        report_name = str(payload.get("report_name", "")).strip()
        if not report_name:
            return {"ok": False, "screen": "report_center", "error": "report_name is required for print"}

        req = GlobalReportRequest(
            report_name=report_name,
            role=str(user_role or "").strip(),
            from_date=(str(payload.get("from_date")).strip() if payload.get("from_date") else None),
            to_date=(str(payload.get("to_date")).strip() if payload.get("to_date") else None),
            as_of_date=(str(payload.get("as_of_date")).strip() if payload.get("as_of_date") else None),
            sections=(payload.get("sections") or []),
            filters=(payload.get("filters") or {}),
        )

        if not isinstance(req.sections, list):
            return {"ok": False, "screen": "report_center", "error": "sections must be a list"}
        if not isinstance(req.filters, dict):
            return {"ok": False, "screen": "report_center", "error": "filters must be an object/dict"}

        try:
            out = generate_report(req)
            out["ok"] = True
            out["screen"] = "report_center"
            out["user"] = user_id or "(unknown)"
            return out
        except Exception as e:
            return {"ok": False, "screen": "report_center", "error": str(e)}

    # --------------------------
    # SUPERVISOR SIGN-OFF
    # --------------------------
    if mode == "signoff":
        supervisor_id = str(payload.get("supervisor_id", "")).strip()
        report_name = str(payload.get("report_name", "")).strip()
        business_date = str(payload.get("as_of_date", "")).strip()

        if not supervisor_id:
            return {"ok": False, "screen": "report_center", "error": "supervisor_id is required for signoff"}
        if not report_name:
            return {"ok": False, "screen": "report_center", "error": "report_name is required for signoff"}
        if not business_date:
            return {"ok": False, "screen": "report_center", "error": "as_of_date is required for signoff"}

        # 1) Generate the report (ensures integrity hash corresponds to what is being signed)
        req = GlobalReportRequest(
            report_name=report_name,
            role=str(user_role or "").strip(),
            as_of_date=business_date,
            sections=(payload.get("sections") or []),
            filters=(payload.get("filters") or {}),
        )

        if not isinstance(req.sections, list):
            return {"ok": False, "screen": "report_center", "error": "sections must be a list"}
        if not isinstance(req.filters, dict):
            return {"ok": False, "screen": "report_center", "error": "filters must be an object/dict"}

        try:
            out = generate_report(req)
        except Exception as e:
            return {"ok": False, "screen": "report_center", "error": f"report generation failed: {e}"}

        integrity = (out or {}).get("_integrity") or {}

        # 2) Persist immutable signoff record
        try:
            from engine.reporting.supervisor_signoff import sign_off_report

            signed = sign_off_report(
                supervisor_id=supervisor_id,
                report_name=report_name,
                business_date=business_date,
                integrity_block=integrity,
            )
            signed["screen"] = "report_center"
            signed["report_name"] = report_name
            signed["business_date"] = business_date
            signed["integrity_sha256"] = integrity.get("sha256")
            return signed
        except Exception as e:
            return {"ok": False, "screen": "report_center", "error": str(e)}

    return {"ok": False, "screen": "report_center", "error": "mode must be 'list', 'print', or 'signoff'"}