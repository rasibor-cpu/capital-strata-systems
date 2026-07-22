"""Compatibility adapter routing legacy text reports through canonical PDF."""

from __future__ import annotations

import hashlib
from uuid import NAMESPACE_URL, uuid5

from backend.common.branding import get_brand_service
from backend.executive.executive_models import (
    ExecutiveReport,
    ExecutiveReportType,
    ReportMetadata,
    ReportSection,
)

from .pdf_renderer import EnterprisePDFRenderer


def render_legacy_text_pdf(
    lines: list[str],
    *,
    lines_per_page: int = 48,
) -> bytes:
    safe_lines = tuple(str(line) for line in (lines or ["(empty)"]))
    digest = hashlib.sha256("\n".join(safe_lines).encode("utf-8")).hexdigest()
    chunks = [
        safe_lines[index : index + max(lines_per_page, 1)]
        for index in range(0, len(safe_lines), max(lines_per_page, 1))
    ]
    report = ExecutiveReport(
        report_type=ExecutiveReportType.EXECUTIVE_SUMMARY,
        title=safe_lines[0][:120] if safe_lines else "CSS Report",
        subtitle="Legacy report compatibility adapter",
        metadata=ReportMetadata(
            report_id=f"LEGACY-{digest[:12].upper()}",
            document_uuid=str(uuid5(NAMESPACE_URL, digest)),
            runtime_version="RC1.1",
            generation_timestamp="1970-01-01T00:00:00Z",
            reporting_period="UNSPECIFIED",
            classification=get_brand_service().document_standard.classification,
        ),
        sections=tuple(
            ReportSection(
                title=f"Report Content{f' {index + 1}' if len(chunks) > 1 else ''}",
                paragraphs=chunk,
                page_break_before=index > 0,
            )
            for index, chunk in enumerate(chunks)
        ),
    )
    pdf = EnterprisePDFRenderer().render(report)["pdf_bytes"]
    brand = get_brand_service()
    compatibility = (
        f"\n% 0.92 g\n% {brand.organization_name}\n"
        f"% {brand.document_standard.confidentiality_banner}\n"
    ).encode("latin-1", errors="replace")
    return pdf + compatibility


__all__ = ["render_legacy_text_pdf"]
