"""CSS Institutional Reports Center service."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from backend.reports_center.archive import ReportArchiveStore
from backend.reports_center.audit import ReportAuditLog
from backend.reports_center.constants import SAFETY_LOCKS, SCHEMA_VERSION
from backend.reports_center.pdf_renderer import CSSReportPDFRenderer
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
        self.pdf_renderer = CSSReportPDFRenderer()

    def home(self, *, role: str = "VIEWER", user_id: str = "") -> dict[str, Any]:
        auth = self.access.authorization_status(role, user_id=user_id)
        recent = self.archive.list_recent(limit=15)
        failed = self.archive.list_failed(limit=10)
        # Latest morning brief pointer + Phase 176J readiness snapshot
        latest_brief = None
        deb_readiness = None
        mb = self.repo_root / "artifacts/runtime_reports/morning_briefings"
        if mb.is_dir():
            latest_files = sorted(mb.rglob("latest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if latest_files:
                try:
                    latest_brief = json.loads(latest_files[0].read_text(encoding="utf-8"))
                except Exception:
                    latest_brief = None
            session_path = mb / "readiness" / "latest_session.json"
            if session_path.is_file():
                try:
                    deb_readiness = json.loads(session_path.read_text(encoding="utf-8"))
                except Exception:
                    deb_readiness = None
        if deb_readiness is None:
            try:
                from backend.executive_intelligence.service import ExecutiveIntelligenceEngine

                deb_readiness = ExecutiveIntelligenceEngine(repo_root=self.repo_root).readiness()
            except Exception:
                deb_readiness = {"status": "UNAVAILABLE", "waiting_for": ["Waiting for Runtime"]}
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
            "executive_brief_readiness": deb_readiness,
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
        payload: dict[str, Any] = {
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
        if report_code == "daily_executive_brief":
            from backend.executive_intelligence.service import ExecutiveIntelligenceEngine

            engine = ExecutiveIntelligenceEngine(repo_root=self.repo_root)
            deb_ready = engine.readiness()
            payload["executive_brief_readiness"] = deb_ready
            payload["freshness"] = deb_ready.get("status")
            payload["waiting_for"] = deb_ready.get("waiting_for") or []
            payload["waiting_labels"] = deb_ready.get("waiting_labels") or []
            session_path = (
                self.repo_root
                / "artifacts/runtime_reports/morning_briefings/readiness/latest_session.json"
            )
            if session_path.is_file():
                try:
                    payload["readiness_session"] = json.loads(session_path.read_text(encoding="utf-8"))
                except Exception:
                    payload["readiness_session"] = None
        return payload

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
        pdf_result: dict[str, Any] = {
            "pdf_status": "NOT_ATTACHED",
            "pdf_available": False,
            "printable_status": "PARTIAL",
        }
        # Daily executive brief already archived under morning_briefings — record bridge only
        if report_code == "daily_executive_brief":
            archive_meta = {
                "bridge": "morning_briefings",
                "external": produced.get("external_identity") or produced.get("bridge_archive"),
            }
            report_id = f"cssrpt_executive_daily_executive_brief_{report_date}_bridge"
            produced["report_id"] = report_id
            # Phase 175 PDF remains canonical for FINAL briefs; expose bridge endpoint.
            if str(produced.get("report_status") or "").upper() == "FINAL":
                pdf_result = {
                    "pdf_status": "OK",
                    "pdf_available": True,
                    "printable_status": "COMPLETE",
                    "pdf_bytes_endpoint": f"/api/v1/executive-brief/{report_date}/pdf",
                    "note": "Executive Brief PDF served by Phase 175 distribution API.",
                    "primary_human_format": "PDF",
                }
            else:
                pdf_result = {
                    "pdf_status": "UNAVAILABLE",
                    "pdf_available": False,
                    "printable_status": "PARTIAL",
                    "pdf_failure_reason": "brief_not_final",
                    "note": "Official Executive Brief PDF requires FINAL status (Phase 175).",
                }
        elif persist:
            # Render plain-English HTML/PDF before archive so report.html is narrative, not dump.
            defn_dict = definition.as_dict()
            narrative_html = ""
            pdf_bytes = None
            pdf_meta = None
            try:
                rendered = self.pdf_renderer.render(
                    produced,
                    definition=defn_dict,
                    printed_by=f"{user_id}/{role}",
                )
                narrative_html = str(rendered.get("html") or "")
                pdf_bytes = rendered["pdf_bytes"]
                pdf_meta = {
                    "generated_at_utc": rendered["generated_at_utc"],
                    "renderer_version": rendered["renderer_version"],
                    "narrative_adapter": rendered["narrative_adapter"],
                    "page_count": rendered["page_count"],
                }
                pdf_result = {
                    "pdf_status": "OK",
                    "pdf_available": True,
                    "printable_status": "COMPLETE",
                    "pdf_sha256": rendered["pdf_sha256"],
                    "page_count": rendered["page_count"],
                    "renderer_version": rendered["renderer_version"],
                    "narrative_adapter": rendered["narrative_adapter"],
                    "primary_human_format": "PDF",
                }
            except Exception as exc:
                pdf_result = {
                    "pdf_status": "FAILED",
                    "pdf_available": False,
                    "printable_status": "PARTIAL",
                    "pdf_failure_reason": str(exc)[:200],
                    "primary_human_format": "PDF",
                }
                # Official reports: PDF failure blocks distribution claim but not canonical archive.
                if definition.official_report:
                    pdf_result["distribution_blocked"] = True
                    pdf_result["note"] = (
                        "Official report PDF failure blocks distribution; canonical archive preserved."
                    )

            # PDF status fields are annotated after canonical report_hash in archive.store/attach_pdf.
            archive_meta = self.archive.publish(
                family=definition.category,
                report_type=report_code,
                report_date=report_date,
                payload=dict(produced),
                validation={
                    "finalization_allowed": produced.get("report_status") == "FINAL",
                    "report_status": produced.get("report_status"),
                },
                markdown=str(produced.get("markdown") or ""),
                html=narrative_html or str(produced.get("html") or ""),
                csv_text=str(produced.get("csv") or ""),
                pdf_bytes=pdf_bytes,
                pdf_meta=pdf_meta,
                created_by=user_id,
                created_reason="reports_center_generate",
            )
            if pdf_result.get("pdf_status") == "FAILED":
                self.archive.attach_pdf(
                    archive_meta["report_id"],
                    b"",
                    failure_reason=str(pdf_result.get("pdf_failure_reason") or "pdf_render_failed"),
                )
                self.audit.record(
                    action="pdf_render",
                    outcome="FAILED",
                    actor_id=user_id,
                    actor_role=role,
                    report_id=archive_meta["report_id"],
                    report_type=report_code,
                    failure_reason=str(pdf_result.get("pdf_failure_reason") or "")[:200],
                )
            produced["report_id"] = archive_meta["report_id"]
            produced["report_version"] = archive_meta["report_version"]
            produced["report_hash"] = archive_meta["report_hash"]
            produced["archive_ref"] = archive_meta["archive_ref"]
            pdf_result["pdf_endpoint"] = f"/api/v1/reports/{archive_meta['report_id']}/pdf"
            if archive_meta.get("pdf"):
                pdf_result["pdf"] = archive_meta["pdf"]
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
            "primary_human_format": definition.primary_human_format or "PDF",
            "technical_export_formats": list(definition.technical_export_formats),
            "pdf": pdf_result,
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
        pdf_status = str(data.get("pdf_status") or "NOT_ATTACHED")
        pdf_available = pdf_status == "OK" and self.archive.read_pdf(report_id) is not None
        return {
            "status": "OK",
            "report_id": report_id,
            "printable": bool(definition.printable) if definition else True,
            "official_print_allowed": official_print,
            "diagnostic_preview_only": not official_print,
            "html_endpoint": f"/api/v1/reports/{report_id}/print",
            "pdf_endpoint": f"/api/v1/reports/{report_id}/pdf",
            "primary_human_format": (definition.primary_human_format if definition else "PDF"),
            "technical_export_formats": list(definition.technical_export_formats) if definition else [],
            "pdf_status": pdf_status,
            "pdf_available": pdf_available,
            "printable_status": data.get("printable_status") or ("COMPLETE" if pdf_available else "PARTIAL"),
            "pdf_failure_reason": data.get("pdf_failure_reason"),
            "requires_permission": required,
            **SAFETY_LOCKS,
        }

    def pdf_bytes(self, report_id: str, *, role: str = "VIEWER", user_id: str = "anonymous") -> dict[str, Any]:
        """Return native PDF bytes when archived; never claim HTML fallback as PDF."""
        info = self.print_info(report_id, role=role, user_id=user_id)
        if info.get("status") != "OK":
            return info
        data = self.archive.retrieve(report_id) or {}
        definition = by_code(str(data.get("report_type") or ""))
        # Bridge DEB to Phase 175 when requested via reports IDs that are not in reports archive.
        if str(data.get("report_type") or "") == "daily_executive_brief" or str(report_id).startswith(
            "cssrpt_executive_"
        ):
            return {
                "status": "BRIDGE",
                "pdf_bytes_endpoint": f"/api/v1/executive-brief/{data.get('report_date') or ''}/pdf",
                "note": "Executive Brief PDF served by Phase 175 distribution API.",
                **info,
            }
        raw = self.archive.read_pdf(report_id)
        if raw is None:
            # Attempt on-demand render for older archives without PDF
            if definition and definition.pdf_supported:
                try:
                    rendered = self.pdf_renderer.render(
                        data,
                        definition=definition.as_dict(),
                        printed_by=f"{user_id}/{role}",
                    )
                    self.archive.attach_pdf(
                        report_id,
                        rendered["pdf_bytes"],
                        pdf_meta={
                            "generated_at_utc": rendered["generated_at_utc"],
                            "renderer_version": rendered["renderer_version"],
                            "narrative_adapter": rendered["narrative_adapter"],
                            "page_count": rendered["page_count"],
                        },
                    )
                    raw = rendered["pdf_bytes"]
                    info["pdf_status"] = "OK"
                    info["pdf_available"] = True
                    info["printable_status"] = "COMPLETE"
                except Exception as exc:
                    self.archive.attach_pdf(report_id, b"", failure_reason=str(exc)[:200])
                    self.audit.record(
                        action="pdf_render",
                        outcome="FAILED",
                        actor_id=user_id,
                        actor_role=role,
                        report_id=report_id,
                        report_type=str(data.get("report_type") or ""),
                        failure_reason=str(exc)[:200],
                    )
                    return {
                        "status": "FAILED",
                        "pdf_status": "FAILED",
                        "pdf_available": False,
                        "printable_status": "PARTIAL",
                        "pdf_failure_reason": str(exc)[:200],
                        **{k: v for k, v in info.items() if k != "status"},
                        **SAFETY_LOCKS,
                    }
            else:
                return {
                    "status": "UNAVAILABLE",
                    "pdf_status": "UNAVAILABLE",
                    "pdf_available": False,
                    "note": "PDF not archived for this report.",
                    **{k: v for k, v in info.items() if k != "status"},
                    **SAFETY_LOCKS,
                }
        self.audit.record(
            action="pdf_export",
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
        return {
            "status": "OK",
            "content_type": "application/pdf",
            "pdf_bytes": raw,
            "filename": f"{report_id}.pdf",
            "pdf_status": "OK",
            "pdf_available": True,
            **{k: v for k, v in info.items() if k not in {"status", "pdf_status", "pdf_available"}},
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
