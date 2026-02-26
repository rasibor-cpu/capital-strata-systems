"""
backend/app/screens/report_center.py

Report Center Screen (Global)
-----------------------------
A reusable screen handler any UI route can call to:
- list available reports (authority-gated)
- print a selected report with timeframe/sections/filters

This is the "print from anywhere" backbone.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List

from backend.app.reporting_api import (
    list_available_reports,
    generate_report,
    GlobalReportRequest,
)


def report_center_handler(
    payload: Dict[str, Any],
    user_role: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    payload:
      mode: "list" | "print"
      report_name: str
      from_date/to_date/as_of_date: optional
      sections: optional list[str]
      filters: optional dict
    """
    mode = payload.get("mode", "list")

    if mode == "list":
        return list_available_reports(user_role)

    if mode != "print":
        return {"ok": False, "error": "mode must be 'list' or 'print'"}

    report_name = payload.get("report_name")
    if not report_name:
        return {"ok": False, "error": "report_name is required for print"}

    sections = payload.get("sections") or []
    if not isinstance(sections, list):
        return {"ok": False, "error": "sections must be a list"}

    filters = payload.get("filters") or {}
    if not isinstance(filters, dict):
        return {"ok": False, "error": "filters must be an object/dict"}

    req = GlobalReportRequest(
        report_name=str(report_name),
        role=str(user_role),
        from_date=payload.get("from_date"),
        to_date=payload.get("to_date"),
        as_of_date=payload.get("as_of_date"),
        sections=[str(s) for s in sections],
        filters=filters,
    )

    out = generate_report(req)

    return {
        "ok": True,
        "screen": "report_center",
        "user": user_id or "(unknown)",
        **out,
    }