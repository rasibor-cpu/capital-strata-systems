"""CSS Institutional Reports Center service."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from backend.reports_center.archive import ReportArchiveStore
from backend.reports_center.audit import ReportAuditLog
from backend.reports_center.constants import SAFETY_LOCKS, SCHEMA_VERSION
from backend.reports_center.producers import produce, utc_today, validate_filters
from backend.reports_center.rbac import ReportsAccessControl
from backend.reports_center.registry import by_code, catalog_payload, category_menu


class ReportsCenterService:
    def __init__(
        self,
        *,
        repo_root: Path | str | None = None,
        archive_root: Path | str | None = None,
        audit_root: Path | str | None = None,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        self.archive = ReportArchiveStore(
            archive_root
            if archive_root
            else self.repo_root / "artifacts/runtime_reports/reports"
        )
        self.audit = ReportAuditLog(
            audit_root if audit_root else self.repo_root / "artifacts/runtime_reports/report_audit"
        )
        self.access = ReportsAccessControl()

    def home(self, *, role: str = "VIEWER", user_id: str = "") -> dict[str, Any]:
        auth = self.access.authorization_status(role, user_id=user_id)
        recent = self.archive.list_recent(limit=15)
        failed = self.archive.list_failed(limit=10)
        # Latest morning brief pointer
        latest_brief = None
        mb = self.repo_root / "artifacts/runtime_reports/morning_briefings"
        if mb.is_dir():
            latest_files = sorted(mb.rglob("latest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if latest_files:
                try:
                    latest_brief = json.loads(latest_files[0].read_text(encoding="utf-8"))
                except Exception:
                    latest_brief = None
        cat = catalog_payload()
        from backend.reports_center.capabilities import ui_report_definition
        from backend.reports_center.registry import all_definitions

        access = self.access
        ui_rows = [ui_report_definition(d, role=role, access=access) for d in all_definitions()]
        generatable = [r for r in ui_rows if r.get("can_generate")]
        return {
            "schema_version": SCHEMA_VERSION,
            "title": "CSS Institutional Reports Center",
            "categories": category_menu(),
            "frequently_used": generatable[:12],
            "latest_daily_executive_brief": latest_brief,
            "recent_reports": recent,
            "report_generation_failures": failed,
            "reports_awaiting_validation": [],
            "counts_by_category": cat["counts_by_category"],
            "total_registered": cat["total_registered"],
            "authorization": auth,
            "archive_health": {
                "reports_archive_present": self.archive.root.is_dir(),
                "recent_count": len(recent),
                "failed_count": len(failed),
            },
            "email_policy_default": "EMAIL_DISABLED",
            **SAFETY_LOCKS,
        }

    def readiness(self, report_code: str, *, role: str = "VIEWER") -> dict[str, Any]:
        definition = by_code(report_code)
        if definition is None:
            return {"status": "NOT_FOUND", "report_code": report_code}
        if not self.access.can_view_report(role, definition.required_view_permission):
            return {"status": "DENIED", "report_code": report_code, "reason": "view_denied"}
        from backend.reports_center.capabilities import evaluate_report_capabilities, ui_report_definition

        caps = evaluate_report_capabilities(definition, role=role, access=self.access)
        ui_def = ui_report_definition(definition, role=role, access=self.access)
        return {
            "status": "OK",
            "report_code": report_code,
            "definition": definition.as_dict(),
            "ui_definition": ui_def,
            "generatable": caps["generatable"],
            "can_generate": caps["can_generate"],
            "generate_label": caps["generate_label"],
            "generate_blocked_reason": caps["generate_blocked_reason"],
            "required_evidence": list(definition.evidence_sources),
            "evidence_availability": (
                "KNOWN" if caps["evidence_contract_supported"] else "INSUFFICIENT_OR_UNREGISTERED"
            ),
            "freshness": "EVALUATED_AT_GENERATION",
            "limitations": definition.limitations,
            "validation_readiness": caps["generatable"],
            "permissions": {
                "view": definition.required_view_permission,
                "generate": definition.required_generate_permission,
                "print": definition.required_print_permission,
                "email": definition.required_email_permission or "EMAIL_DISABLED",
            },
            "capabilities": caps,
            "confidentiality_classification": (
                "CONFIDENTIAL_FINANCIAL" if definition.contains_financial_values else "INTERNAL"
            ),
            "official_report": definition.official_report,
            "advisory_only": definition.advisory_only,
            "email_policy": definition.email_policy,
            **SAFETY_LOCKS,
        }

    def generate(
        self,
        report_code: str,
        *,
        filters: dict[str, Any] | None = None,
        role: str = "VIEWER",
        user_id: str = "anonymous",
        persist: bool = True,
    ) -> dict[str, Any]:
        definition = by_code(report_code)
        if definition is None:
            self.audit.record(
                action="generate",
                outcome="DENIED",
                actor_id=user_id,
                actor_role=role,
                report_type=report_code,
                failure_reason="unknown_report",
            )
            return {"status": "NOT_FOUND", "report_code": report_code}
        if not definition.generatable:
            self.audit.record(
                action="generate",
                outcome="DENIED",
                actor_id=user_id,
                actor_role=role,
                report_type=report_code,
                permission_used=definition.required_generate_permission,
                failure_reason=f"status_{definition.status}",
            )
            return {
                "status": "NOT_GENERATABLE",
                "report_code": report_code,
                "catalogue_status": definition.status,
                "limitations": definition.limitations,
                **SAFETY_LOCKS,
            }
        if not self.access.can_generate(role, definition.required_generate_permission):
            self.audit.record(
                action="generate",
                outcome="DENIED",
                actor_id=user_id,
                actor_role=role,
                report_type=report_code,
                permission_used=definition.required_generate_permission,
                failure_reason="generate_denied",
            )
            return {"status": "DENIED", "reason": "generate_denied", **SAFETY_LOCKS}

        try:
            safe_filters = validate_filters(filters)
            produced = produce(report_code, filters=safe_filters, repo_root=self.repo_root)
        except ValueError as exc:
            self.audit.record(
                action="generate",
                outcome="FAILED",
                actor_id=user_id,
                actor_role=role,
                report_type=report_code,
                failure_reason=str(exc)[:200],
            )
            return {"status": "FAILED", "reason": str(exc), **SAFETY_LOCKS}
        except Exception as exc:
            self.audit.record(
                action="generate",
                outcome="FAILED",
                actor_id=user_id,
                actor_role=role,
                report_type=report_code,
                failure_reason=type(exc).__name__,
            )
            return {"status": "FAILED", "reason": "producer_error", "detail": type(exc).__name__, **SAFETY_LOCKS}

        report_date = str(produced.get("report_date") or safe_filters.get("report_date") or utc_today())
        produced["report_type"] = report_code
        produced["official_report"] = bool(definition.official_report and produced.get("report_status") == "FINAL")
        produced["advisory_only"] = True
        produced["contains_financial_values"] = definition.contains_financial_values
        produced["confidentiality_classification"] = (
            "CONFIDENTIAL_FINANCIAL" if definition.contains_financial_values else "INTERNAL"
        )
        produced["schema_version"] = SCHEMA_VERSION

        archive_meta = None
        # Daily executive brief already archived under morning_briefings — record bridge only
        if report_code == "daily_executive_brief":
            archive_meta = {
                "bridge": "morning_briefings",
                "external": produced.get("external_identity") or produced.get("bridge_archive"),
            }
            report_id = f"cssrpt_executive_daily_executive_brief_{report_date}_bridge"
            produced["report_id"] = report_id
        elif persist:
            archive_meta = self.archive.publish(
                family=definition.category,
                report_type=report_code,
                report_date=report_date,
                payload=produced,
                validation={
                    "finalization_allowed": produced.get("report_status") == "FINAL",
                    "report_status": produced.get("report_status"),
                },
                markdown=str(produced.get("markdown") or ""),
                html=str(produced.get("html") or ""),
                csv_text=str(produced.get("csv") or ""),
                created_by=user_id,
                created_reason="reports_center_generate",
            )
            produced["report_id"] = archive_meta["report_id"]
            produced["report_version"] = archive_meta["report_version"]
            produced["report_hash"] = archive_meta["report_hash"]
            produced["archive_ref"] = archive_meta["archive_ref"]
        else:
            produced["report_id"] = f"cssrpt_draft_{report_code}_{report_date}"
            produced["report_status"] = produced.get("report_status") or "DRAFT"

        self.audit.record(
            action="generate",
            outcome="OK" if produced.get("report_status") == "FINAL" else "FAILED",
            actor_id=user_id,
            actor_role=role,
            permission_used=definition.required_generate_permission,
            report_id=str(produced.get("report_id") or ""),
            report_type=report_code,
            report_version=str(produced.get("report_version") or ""),
            report_hash=str(produced.get("report_hash") or ""),
            official=produced.get("official_report"),
        )

        return {
            "status": "OK",
            "report_id": produced.get("report_id"),
            "report_type": report_code,
            "report_date": report_date,
            "report_status": produced.get("report_status"),
            "version": produced.get("report_version"),
            "hash": produced.get("report_hash"),
            "blockers": [] if produced.get("report_status") == "FINAL" else [produced.get("limitations") or "generation_failed"],
            "archive": archive_meta,
            "available_formats": list(definition.supported_formats),
            "authorized_actions": self._actions_for(definition, role, produced),
            "report": produced,
            **SAFETY_LOCKS,
        }

    def retrieve(self, report_id: str, *, role: str = "VIEWER") -> dict[str, Any]:
        if not self.access.can_view_catalog(role):
            return {"status": "DENIED"}
        data = self.archive.retrieve(report_id)
        if data is None:
            return {"status": "NOT_FOUND", "report_id": report_id}
        definition = by_code(str(data.get("report_type") or ""))
        if definition and not self.access.can_view_report(role, definition.required_view_permission):
            return {"status": "DENIED", "report_id": report_id}
        self.audit.record(
            action="view",
            outcome="OK",
            actor_id="system",
            actor_role=role,
            report_id=report_id,
            report_type=str(data.get("report_type") or ""),
            report_hash=str(data.get("report_hash") or ""),
        )
        return {"status": "OK", "report": data, **SAFETY_LOCKS}

    def list_library(self, *, filters: dict[str, Any] | None = None, role: str = "VIEWER") -> dict[str, Any]:
        if not self.access.can_view_catalog(role):
            return {"status": "DENIED", "reports": []}
        filters = filters or {}
        limit = int(filters.get("limit") or 50)
        if str(filters.get("view") or "").lower() == "latest":
            limit = min(limit, 20)
        items = self.archive.list_recent(limit=limit)
        if filters.get("category"):
            items = [i for i in items if i.get("report_family") == filters["category"] or i.get("category") == filters["category"]]
        if filters.get("report_type"):
            items = [i for i in items if i.get("report_type") == filters["report_type"]]
        if filters.get("status"):
            items = [i for i in items if str(i.get("report_status")).upper() == str(filters["status"]).upper()]
        if filters.get("report_id"):
            items = [i for i in items if i.get("report_id") == filters["report_id"]]
        return {"status": "OK", "count": len(items), "reports": items, "view": filters.get("view") or "all", **SAFETY_LOCKS}

    def print_info(self, report_id: str, *, role: str = "VIEWER", user_id: str = "anonymous") -> dict[str, Any]:
        data = self.archive.retrieve(report_id)
        if data is None:
            return {"status": "NOT_FOUND"}
        definition = by_code(str(data.get("report_type") or ""))
        required = definition.required_print_permission if definition else "reports_print_all"
        if not self.access.can_print(role, required):
            self.audit.record(
                action="print",
                outcome="DENIED",
                actor_id=user_id,
                actor_role=role,
                report_id=report_id,
                permission_used=required,
                failure_reason="print_denied",
            )
            return {"status": "DENIED", "reason": "print_denied"}
        status = str(data.get("report_status") or "").upper()
        official_print = status == "FINAL"
        return {
            "status": "OK",
            "report_id": report_id,
            "printable": bool(definition.printable) if definition else True,
            "official_print_allowed": official_print,
            "diagnostic_preview_only": not official_print,
            "html_endpoint": f"/api/v1/reports/{report_id}/print",
            "pdf_endpoint": f"/api/v1/reports/{report_id}/pdf",
            "requires_permission": required,
            **SAFETY_LOCKS,
        }

    def printable_html(self, report_id: str, *, role: str = "VIEWER", user_id: str = "anonymous") -> dict[str, Any]:
        info = self.print_info(report_id, role=role, user_id=user_id)
        if info.get("status") != "OK":
            return info
        data = self.archive.retrieve(report_id) or {}
        definition = by_code(str(data.get("report_type") or ""))
        body = data.get("html")
        if not body:
            body = _html_wrap(
                str(data.get("title") or data.get("report_type") or "Report"),
                json.dumps(data.get("content") or data, indent=2, sort_keys=True, default=str),
                limitations=str(data.get("limitations") or ""),
                report_id=report_id,
                version=str(data.get("report_version") or ""),
                report_hash=str(data.get("report_hash") or ""),
                printed_by=f"{user_id}/{role}",
                status=str(data.get("report_status") or ""),
            )
        else:
            # Ensure footer metadata
            body = str(body)
        if str(data.get("report_status") or "").upper() != "FINAL":
            body = (
                '<div style="border:3px solid #991b1b;padding:10px;margin:10px 0;">'
                "DIAGNOSTIC PREVIEW ONLY — not an official printable FINAL report."
                "</div>"
            ) + body
        self.audit.record(
            action="print",
            outcome="OK",
            actor_id=user_id,
            actor_role=role,
            permission_used=(definition.required_print_permission if definition else "reports_print_all"),
            report_id=report_id,
            report_type=str(data.get("report_type") or ""),
            report_version=str(data.get("report_version") or ""),
            report_hash=str(data.get("report_hash") or ""),
            official=str(data.get("report_status") or "").upper() == "FINAL",
        )
        return {"status": "OK", "content_type": "text/html", "html": body, **SAFETY_LOCKS}

    def export_json(self, report_id: str, *, role: str = "VIEWER", user_id: str = "anonymous") -> dict[str, Any]:
        if not self.access.can_export(role):
            return {"status": "DENIED"}
        data = self.archive.retrieve(report_id)
        if data is None:
            return {"status": "NOT_FOUND"}
        self.audit.record(
            action="export_json",
            outcome="OK",
            actor_id=user_id,
            actor_role=role,
            permission_used="reports_export",
            report_id=report_id,
            report_type=str(data.get("report_type") or ""),
            report_hash=str(data.get("report_hash") or ""),
        )
        return {"status": "OK", "export": data, **SAFETY_LOCKS}

    def audit_history(self, report_id: str | None = None, *, role: str = "VIEWER") -> dict[str, Any]:
        if not self.access.can_view_audit(role):
            return {"status": "DENIED"}
        return {"status": "OK", "events": self.audit.list_events(report_id=report_id, limit=200), **SAFETY_LOCKS}

    def verify_integrity(self, report_id: str, *, role: str = "VIEWER", user_id: str = "anonymous") -> dict[str, Any]:
        if not self.access.can_view_audit(role):
            return {"status": "DENIED"}
        result = self.archive.verify_integrity(report_id)
        self.audit.record(
            action="verify_integrity",
            outcome=result.get("outcome") or result.get("status") or "UNKNOWN",
            actor_id=user_id,
            actor_role=role,
            report_id=report_id,
            report_hash=str(result.get("stored_hash") or ""),
        )
        return result

    def _actions_for(self, definition, role: str, produced: dict[str, Any]) -> list[str]:
        actions = ["view"]
        if definition.downloadable and self.access.can_export(role):
            actions.append("download_json")
            if "CSV" in definition.supported_formats and produced.get("csv"):
                actions.append("download_csv")
        if definition.printable and self.access.can_print(role, definition.required_print_permission):
            actions.extend(["print_preview", "print"])
            if "PDF" in definition.supported_formats:
                actions.append("download_pdf")
        if definition.emailable and self.access.can_email(role, definition.required_email_permission):
            actions.append("email")
        actions.append("versions")
        if self.access.can_view_audit(role):
            actions.append("audit_history")
            actions.append("verify_integrity")
        return actions


def _html_wrap(
    title: str,
    body: str,
    *,
    limitations: str = "",
    report_id: str = "",
    version: str = "",
    report_hash: str = "",
    printed_by: str = "",
    status: str = "",
) -> str:
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lim = f"<p><strong>Limitations:</strong> {html.escape(limitations)}</p>" if limitations else ""
    footer = (
        f"<footer style='margin-top:24px;border-top:1px solid #ccc;padding-top:8px;font-size:12px;'>"
        f"Report ID: {html.escape(report_id)} | Version: {html.escape(version)} | "
        f"Hash: {html.escape(report_hash)} | Status: {html.escape(status)} | "
        f"Printed by: {html.escape(printed_by)} | Print timestamp: {ts}<br/>"
        f"ADVISORY ONLY — confidentiality: INTERNAL/CONFIDENTIAL as marked on report."
        f"</footer>"
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title></head><body>"
        f"<h1>{html.escape(title)}</h1>"
        "<div style='border:2px solid #b45309;padding:8px;'>ADVISORY ONLY — live trading blocked.</div>"
        f"{lim}<pre>{html.escape(body)}</pre>{footer}</body></html>"
    )
