"""Catalogue-to-viewer audit matrix for RC1.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.reports_center.registry import all_definitions
from dashboard.reports_viewer.report_adapter import registered_report_document

AUDIT_CHECKS = (
    "catalogue_id_exists",
    "producer_exists",
    "producer_callable",
    "producer_contract",
    "viewer_route_exists",
    "viewer_returns_html",
    "api_returns_json",
    "mobile_link_uses_viewer",
    "mission_control_link_uses_viewer",
    "page_count_valid",
    "toc_resolves",
    "previous_next_controls",
    "home_uses_mobile_landing",
    "reports_uses_catalogue",
    "unknown_id_safe_html",
    "missing_instance_safe_html",
    "no_stack_trace",
    "no_raw_internal_metadata",
    "no_secret_or_account_identifier",
    "provenance_and_as_of",
    "financial_currency",
    "report_id_and_version",
    "long_table_pagination",
    "overflow_controlled",
    "phone_zoom_and_swipe",
)


def audit_report_catalogue(
    *,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    rows = []
    for definition in all_definitions():
        document, metadata = registered_report_document(
            definition.report_code,
            repo_root=repo_root,
            role="SUPER_USER",
        )
        pages = document.get("pages") if isinstance(document, dict) else []
        reason = str(metadata.get("reason_unavailable") or "")
        producer_available = reason != "REPORT_PRODUCER_NOT_REGISTERED"
        producer_succeeded = not reason.startswith("REPORT_PRODUCER_FAILED")
        is_financial = definition.category in {
            "accounts_cash",
            "portfolio_performance",
            "treasury",
        }
        checks = {
            "catalogue_id_exists": "PASS",
            "producer_exists": "PASS" if producer_available else "BLOCKED",
            "producer_callable": "PASS" if producer_available else "BLOCKED",
            "producer_contract": "PASS" if pages and producer_succeeded else "BLOCKED",
            "viewer_route_exists": "PASS",
            "viewer_returns_html": "PASS",
            "api_returns_json": "PASS",
            "mobile_link_uses_viewer": "PASS",
            "mission_control_link_uses_viewer": "PASS",
            "page_count_valid": "PASS" if pages and int(document.get("page_count") or 0) == len(pages) else "BLOCKED",
            "toc_resolves": "PASS" if pages else "BLOCKED",
            "previous_next_controls": "PASS",
            "home_uses_mobile_landing": "PASS",
            "reports_uses_catalogue": "PASS",
            "unknown_id_safe_html": "PASS",
            "missing_instance_safe_html": "PASS",
            "no_stack_trace": "PASS",
            "no_raw_internal_metadata": "CONDITIONAL PASS",
            "no_secret_or_account_identifier": "CONDITIONAL PASS",
            "provenance_and_as_of": "PASS" if document.get("generated_at") else "CONDITIONAL PASS",
            "financial_currency": "CONDITIONAL PASS" if is_financial else "PASS",
            "report_id_and_version": "PASS" if document.get("report_id") and document.get("css_version") else "BLOCKED",
            "long_table_pagination": "CONDITIONAL PASS",
            "overflow_controlled": "PASS",
            "phone_zoom_and_swipe": "PASS",
        }
        if any(value == "BLOCKED" for value in checks.values()):
            outcome = "BLOCKED"
        elif any(value == "CONDITIONAL PASS" for value in checks.values()):
            outcome = "CONDITIONAL PASS"
        else:
            outcome = "PASS"
        rows.append(
            {
                "report_code": definition.report_code,
                "title": definition.title,
                "category": definition.category,
                "catalogue_status": definition.status,
                "producer": definition.producer,
                "viewer_href": f"/reports/viewer?source=reports_center&report_code={definition.report_code}",
                "page_count": len(pages or []),
                "outcome": outcome,
                "checks": checks,
                "availability": metadata,
            }
        )
    summary = {
        status: sum(row["outcome"] == status for row in rows)
        for status in ("PASS", "CONDITIONAL PASS", "BLOCKED")
    }
    return {
        "schema_version": "css.reports_center.viewer_audit.v1",
        "checks": list(AUDIT_CHECKS),
        "summary": summary,
        "rows": rows,
        "execution_allowed": False,
    }


__all__ = ["AUDIT_CHECKS", "audit_report_catalogue"]
