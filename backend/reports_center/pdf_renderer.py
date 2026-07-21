"""CSSReportPDFRenderer — shared plain-English PDF rendering (Phase 176G).

Reuses the Phase 175 minimal PDF writer. Does not replace Executive Brief
Phase 175 distribution PDF for morning briefings.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from backend.common.branding import CONFIDENTIALITY_BANNER, get_brand_service
from backend.executive_intelligence.print_report import build_text_pdf, pdf_sha256
from backend.executive_intelligence.sanitizer import contains_secrets, sanitize_payload
from backend.reports_center.constants import SAFETY_LOCKS
from backend.reports_center.narrative import RENDERER_VERSION, build_narrative

CONFIDENTIALITY = CONFIDENTIALITY_BANNER


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CSSReportPDFRenderer:
    """Canonical PDF renderer for Reports Center archived objects."""

    def render(
        self,
        report: Mapping[str, Any],
        *,
        definition: Mapping[str, Any] | None = None,
        printed_by: str = "system",
        print_timestamp_utc: str | None = None,
    ) -> dict[str, Any]:
        """Return PDF bytes + metadata. Failures raise ValueError with reason."""
        clean = sanitize_payload(dict(report))
        has_secrets, secret_paths = contains_secrets(clean)
        if has_secrets:
            raise ValueError(f"secrets_present:{','.join(secret_paths[:5])}")
        ts = print_timestamp_utc or _utc_now()
        narrative = build_narrative(
            clean,
            definition=definition or {},
            printed_by=printed_by,
            generated_at_utc=ts,
        )
        html_doc = self.render_html(narrative, report=clean, printed_by=printed_by, ts=ts)
        lines = self._pdf_lines(narrative, printed_by=printed_by, ts=ts)
        pdf_bytes = build_text_pdf(
            lines,
            watermark_text=get_brand_service().organization_name,
        )
        if not pdf_bytes.startswith(b"%PDF"):
            raise ValueError("pdf_signature_invalid")
        if len(pdf_bytes) < 64:
            raise ValueError("pdf_empty")
        page_count = max(1, (len(lines) + 47) // 48)
        return {
            "status": "OK",
            "pdf_bytes": pdf_bytes,
            "html": html_doc,
            "pdf_sha256": pdf_sha256(pdf_bytes),
            "page_count": page_count,
            "renderer_version": RENDERER_VERSION,
            "narrative_adapter": narrative["adapter"],
            "generated_at_utc": ts,
            "title": narrative["title"],
            "report_id": narrative["report_id"],
            "version": narrative["version"],
            "size": len(pdf_bytes),
            **SAFETY_LOCKS,
        }

    def render_html(
        self,
        narrative: Mapping[str, Any] | None = None,
        *,
        report: Mapping[str, Any] | None = None,
        definition: Mapping[str, Any] | None = None,
        printed_by: str = "system",
        ts: str | None = None,
    ) -> str:
        brand = get_brand_service()
        ts = ts or _utc_now()
        if narrative is None:
            narrative = build_narrative(
                sanitize_payload(dict(report or {})),
                definition=definition or {},
                printed_by=printed_by,
                generated_at_utc=ts,
            )

        def esc(value: Any) -> str:
            return html.escape(str(value if value is not None else "UNAVAILABLE"))

        sections_html = []
        for section in narrative.get("sections") or []:
            paras = "".join(f"<p>{esc(p)}</p>" for p in (section.get("paragraphs") or []))
            sections_html.append(f"<h2>{esc(section.get('heading'))}</h2>{paras}")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{esc(narrative.get('title'))}</title>
  <style>
    @page {{ margin: 18mm; }}
    body {{ font-family: Georgia, "Times New Roman", serif; color: #111; margin: 24px; line-height: 1.35; }}
    .document-page {{ position:relative; isolation:isolate; min-height:250mm; }}
    h1,h2 {{ font-family: Arial, Helvetica, sans-serif; }}
    .banner {{ border: 2px solid #8a1c1c; background: #fff5f5; padding: 10px 12px; margin-bottom: 16px; }}
    .meta {{ font-size: 12px; margin-bottom: 16px; }}
    .footer {{ margin-top: 28px; border-top: 1px solid #999; padding-top: 10px; font-size: 11px; }}
    {brand.watermark_css(page_selector=".document-page")}
  </style>
</head>
<body>
  <main class="document-page">
  {brand.watermark_markup()}
  <h1>{esc(brand.organization_name)}</h1>
  <h2>{esc(narrative.get('title'))}</h2>
  <div class="banner">
    <strong>ADVISORY ONLY</strong> — Live trade execution was not authorized when this report was generated.
    No broker was armed for order execution. Live trading remains blocked by safety policy.
    {esc(CONFIDENTIALITY)}
  </div>
  <div class="meta">
    <div>Report date: {esc(narrative.get('report_date'))}</div>
    <div>Reporting period: {esc(narrative.get('reporting_period'))}</div>
    <div>Report ID: {esc(narrative.get('report_id'))}</div>
    <div>Version: {esc(narrative.get('version'))}</div>
    <div>Status: {esc(narrative.get('status'))}</div>
    <div>Confidentiality: {esc(narrative.get('classification'))}</div>
  </div>
  {''.join(sections_html)}
  <div class="footer">
    <div>Generated by: {esc(printed_by)}</div>
    <div>Timestamp (UTC): {esc(ts)}</div>
    <div>Renderer: {esc(RENDERER_VERSION)}</div>
    <div>Document ID: {esc(narrative.get('report_id'))}</div>
    <div>Runtime version: {esc(narrative.get('version'))}</div>
    <div>{esc(brand.document_standard.confidentiality_banner)}</div>
  </div>
  </main>
</body>
</html>
"""

    def _pdf_lines(self, narrative: Mapping[str, Any], *, printed_by: str, ts: str) -> list[str]:
        brand = get_brand_service()
        lines = [
            brand.organization_name,
            str(narrative.get("title") or "CSS Report"),
            CONFIDENTIALITY,
            "ADVISORY ONLY — Live trade execution was not authorized when this report was generated.",
            "No broker was armed for order execution. Live trading remains blocked by safety policy.",
            "",
            f"Report date: {narrative.get('report_date')}",
            f"Reporting period: {narrative.get('reporting_period')}",
            f"Report ID: {narrative.get('report_id')}",
            f"Version: {narrative.get('version')}",
            f"Report status: {narrative.get('status')}",
            f"Classification: {narrative.get('classification')}",
            "",
        ]
        for section in narrative.get("sections") or []:
            heading = str(section.get("heading") or "")
            if heading.lower() == "technical appendix":
                lines.append("")
                lines.append("--- TECHNICAL APPENDIX (internal codes) ---")
            else:
                lines.append("")
                lines.append(heading.upper())
            for para in section.get("paragraphs") or []:
                text = str(para)
                while text:
                    lines.append(text[:110])
                    text = text[110:]
        lines.extend(
            [
                "",
                f"Generated by: {printed_by}",
                f"Generated timestamp UTC: {ts}",
                f"Renderer: {RENDERER_VERSION}",
                f"Narrative adapter: {narrative.get('adapter')}",
            ]
        )
        return [str(line) for line in lines]
