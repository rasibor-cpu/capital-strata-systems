"""Adapt registered Reports Center output into the canonical paginated viewer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from backend.broker_reporting.page_layout import build_paginated_document
from backend.reports_center.producers import produce, registered_producer_codes
from backend.reports_center.rbac import ReportsAccessControl
from backend.reports_center.registry import by_code
from backend.reports_center.service import ReportsCenterService


def registered_report_document(
    report_code: str,
    *,
    repo_root: Path | str | None = None,
    role: str = "VIEWER",
) -> tuple[dict[str, Any], dict[str, Any]]:
    code = str(report_code or "").strip()
    definition = by_code(code)
    if definition is None:
        return unavailable_report_document(
            report_name=code or "Unknown report",
            status="NOT_FOUND",
            reason="REPORT_NOT_REGISTERED",
            producer=None,
        )
    if not ReportsAccessControl().can_view_report(
        str(role or "VIEWER").upper(),
        definition.required_view_permission,
    ):
        return unavailable_report_document(
            report_name=definition.title,
            status="DENIED",
            reason="REPORT_VIEW_PERMISSION_DENIED",
            producer=definition.producer,
        )
    if code not in registered_producer_codes():
        return unavailable_report_document(
            report_name=definition.title,
            status=definition.status,
            reason="REPORT_PRODUCER_NOT_REGISTERED",
            producer=definition.producer,
        )
    try:
        payload = produce(code, filters={}, repo_root=Path(repo_root or Path.cwd()))
    except Exception as exc:
        return unavailable_report_document(
            report_name=definition.title,
            status=definition.status,
            reason=f"REPORT_PRODUCER_FAILED:{type(exc).__name__}",
            producer=definition.producer,
        )
    document = _extract_document(payload)
    if document is not None:
        return document, _meta(definition.title, "AVAILABLE", None, definition.producer)
    return _payload_document(
        title=definition.title,
        report_id=str(payload.get("report_id") or code),
        payload=payload,
        version=str(payload.get("version") or definition.implementation_phase or "RC1.1"),
    ), _meta(definition.title, str(payload.get("report_status") or definition.status), None, definition.producer)


def archived_report_document(
    report_id: str,
    *,
    role: str,
    repo_root: Path | str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = ReportsCenterService(repo_root=repo_root).retrieve(
        str(report_id or ""),
        role=str(role or "VIEWER"),
    )
    if result.get("status") != "OK" or not isinstance(result.get("report"), Mapping):
        return unavailable_report_document(
            report_name=str(report_id or "Unknown report"),
            status=str(result.get("status") or "NOT_FOUND"),
            reason=str(result.get("reason") or "REPORT_INSTANCE_NOT_FOUND"),
            producer="ReportsCenterService.retrieve",
        )
    report = dict(result["report"])
    document = _extract_document(report)
    if document is not None:
        return document, _meta(
            str(report.get("title") or report_id),
            "AVAILABLE",
            None,
            "ReportsCenterService.retrieve",
        )
    return _payload_document(
        title=str(report.get("title") or report.get("report_type") or report_id),
        report_id=str(report.get("report_id") or report_id),
        payload=report,
        version=str(report.get("version") or report.get("report_version") or "RC1.1"),
    ), _meta(str(report.get("title") or report_id), "AVAILABLE", None, "ReportsCenterService.retrieve")


def unavailable_report_document(
    *,
    report_name: str,
    status: str,
    reason: str,
    producer: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = _meta(report_name, status, reason, producer)
    document = build_paginated_document(
        title=report_name,
        report_id=f"UNAVAILABLE-{_safe_id(report_name)}",
        css_version="RC1.1",
        commit_reference=None,
        generated_at="UNAVAILABLE",
        executive_summary=[
            f"Availability: {status}",
            f"Reason unavailable: {reason}",
            f"Expected producer/source: {producer or 'UNAVAILABLE'}",
            "No report content has been fabricated.",
        ],
        sections=[("Unavailable Report", metadata)],
    ).as_dict()
    return document, metadata


def _extract_document(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    candidates = (
        payload.get("document"),
        (payload.get("content") or {}).get("document")
        if isinstance(payload.get("content"), Mapping)
        else None,
    )
    for candidate in candidates:
        if isinstance(candidate, Mapping) and isinstance(candidate.get("pages"), list):
            return dict(candidate)
    return None


def _payload_document(
    *,
    title: str,
    report_id: str,
    payload: Mapping[str, Any],
    version: str,
) -> dict[str, Any]:
    content = payload.get("content")
    safe_content = content if isinstance(content, (Mapping, list, tuple)) else {
        "status": payload.get("report_status") or payload.get("status") or "AVAILABLE",
        "summary": content or payload.get("limitations") or "Rendered report output.",
    }
    return build_paginated_document(
        title=title,
        report_id=report_id,
        css_version=version,
        commit_reference=None,
        generated_at=str(payload.get("generated_at") or payload.get("report_date") or "UNAVAILABLE"),
        executive_summary=[
            f"Report status: {payload.get('report_status') or payload.get('status') or 'AVAILABLE'}",
            f"As of: {payload.get('generated_at') or payload.get('report_date') or 'UNAVAILABLE'}",
            "Source: Reports Center registered producer",
        ],
        sections=[("Report", safe_content)],
    ).as_dict()


def _meta(
    title: str,
    status: str,
    reason: str | None,
    producer: str | None,
) -> dict[str, Any]:
    return {
        "report_name": title,
        "availability_status": status,
        "reason_unavailable": reason,
        "expected_producer_source": producer,
        "execution_allowed": False,
    }


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in str(value).upper()).strip("-") or "REPORT"


__all__ = [
    "archived_report_document",
    "registered_report_document",
    "unavailable_report_document",
]
