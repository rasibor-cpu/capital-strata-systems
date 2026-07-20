"""
CSS Enterprise Reporting Presentation Standard — paginated document layout.

All broker executive reports render as professionally paginated documents
with identical pagination for browser, mobile, and PDF export.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

SCHEMA_VERSION = "css.enterprise.report.page_layout.v1"
DEFAULT_LINES_PER_PAGE = 42


@dataclass
class ReportPage:
    page_number: int
    page_type: str  # cover | toc | content | summary
    title: str
    lines: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EnterpriseReportDocument:
    title: str
    report_id: str
    css_version: str
    commit_reference: str | None
    generated_at: str
    page_count: int
    pages: list[ReportPage]
    presentation: dict[str, Any]
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "report_id": self.report_id,
            "css_version": self.css_version,
            "commit_reference": self.commit_reference,
            "generated_at": self.generated_at,
            "page_count": self.page_count,
            "pages": [p.as_dict() for p in self.pages],
            "presentation": self.presentation,
            "schema_version": self.schema_version,
        }

    def to_html(self) -> str:
        """PDF-style paginated HTML — page-oriented, minimal continuous scroll."""
        parts = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            f"<title>{_esc(self.title)}</title>",
            "<style>",
            "body{background:#e8e8e8;margin:0;font-family:Georgia,'Times New Roman',serif;}",
            ".page{background:#fff;width:8.5in;min-height:11in;margin:16px auto;padding:0.75in;",
            "box-shadow:0 2px 8px rgba(0,0,0,.15);page-break-after:always;box-sizing:border-box;}",
            "@media print{.page{margin:0;box-shadow:none;}}",
            "h1{font-size:22pt;margin:0 0 12px;} h2{font-size:14pt;margin:18px 0 8px;}",
            ".meta{color:#444;font-size:10pt;margin-bottom:18px;} pre{white-space:pre-wrap;font-size:10pt;}",
            ".footer{margin-top:24px;font-size:9pt;color:#666;border-top:1px solid #ccc;padding-top:8px;}",
            "</style></head><body>",
        ]
        for page in self.pages:
            parts.append("<section class='page'>")
            if page.page_type == "cover":
                parts.append(f"<h1>{_esc(page.title)}</h1>")
            else:
                parts.append(f"<h2>{_esc(page.title)}</h2>")
            parts.append(
                f"<div class='meta'>Report ID: {_esc(self.report_id)} · "
                f"Generated: {_esc(self.generated_at)} · CSS: {_esc(self.css_version)}"
                + (f" · Commit: {_esc(self.commit_reference)}" if self.commit_reference else "")
                + "</div>"
            )
            parts.append("<pre>" + _esc("\n".join(page.lines)) + "</pre>")
            parts.append(
                f"<div class='footer'>Page {page.page_number} of {self.page_count} · "
                "CSS Enterprise Reporting Standard · Advisory only · Execution blocked</div>"
            )
            parts.append("</section>")
        parts.append("</body></html>")
        return "".join(parts)


def build_paginated_document(
    *,
    title: str,
    report_id: str,
    css_version: str,
    commit_reference: str | None,
    generated_at: str,
    executive_summary: Sequence[str],
    sections: Sequence[tuple[str, Any]],
    lines_per_page: int = DEFAULT_LINES_PER_PAGE,
) -> EnterpriseReportDocument:
    pages: list[ReportPage] = []

    # Cover
    cover_lines = [
        title,
        "",
        f"Report ID: {report_id}",
        f"Generated (UTC): {generated_at}",
        f"CSS Version: {css_version}",
        f"Commit: {commit_reference or 'N/A'}",
        "",
        "Classification: Advisory management report",
        "Execution authority: BLOCKED",
        "Trading impact: false",
        "",
        "Canonical Tier-1 Brokers: Coinbase · Binance · OANDA · Questrade",
        "Roadmap exclusion: Interactive Brokers (IBKR)",
    ]
    pages.append(ReportPage(page_number=1, page_type="cover", title=title, lines=cover_lines))

    # Executive summary
    pages.append(
        ReportPage(
            page_number=2,
            page_type="summary",
            title="Executive Summary",
            lines=list(executive_summary),
        )
    )

    # TOC
    toc_lines = [f"{idx}. {name}" for idx, (name, _) in enumerate(sections, start=1)]
    pages.append(ReportPage(page_number=3, page_type="toc", title="Table of Contents", lines=toc_lines))

    # Content sections — paginate by line budget
    for section_title, payload in sections:
        body = _format_payload(payload)
        chunks = _chunk_lines(body, max(8, lines_per_page - 6))
        for i, chunk in enumerate(chunks):
            suffix = f" (continued)" if i else ""
            pages.append(
                ReportPage(
                    page_number=0,  # renumber later
                    page_type="content",
                    title=f"{section_title}{suffix}",
                    lines=chunk,
                )
            )

    for idx, page in enumerate(pages, start=1):
        page.page_number = idx

    return EnterpriseReportDocument(
        title=title,
        report_id=report_id,
        css_version=css_version,
        commit_reference=commit_reference,
        generated_at=generated_at,
        page_count=len(pages),
        pages=pages,
        presentation={
            "mode": "paginated",
            "layout": "pdf_style_pages",
            "scroll_policy": "minimize_continuous_scroll",
            "identical_pagination": ["browser", "mobile", "pdf"],
            "required_elements": [
                "cover_page",
                "executive_summary",
                "table_of_contents",
                "page_numbers",
                "generation_timestamp",
                "css_version",
                "report_id",
                "commit_reference",
            ],
        },
    )


def _format_payload(payload: Any) -> list[str]:
    if isinstance(payload, str):
        return payload.splitlines() or [payload]
    if isinstance(payload, (list, tuple)):
        lines: list[str] = []
        for item in payload:
            if isinstance(item, str):
                lines.append(f"- {item}")
            else:
                lines.extend(json.dumps(item, indent=2, default=str, sort_keys=True).splitlines())
        return lines or ["(empty)"]
    try:
        return json.dumps(payload, indent=2, default=str, sort_keys=True).splitlines()
    except Exception:
        return [str(payload)]


def _chunk_lines(lines: Sequence[str], size: int) -> list[list[str]]:
    items = list(lines) or ["(empty)"]
    return [items[i : i + size] for i in range(0, len(items), size)]


def _esc(value: Any) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


__all__ = [
    "DEFAULT_LINES_PER_PAGE",
    "EnterpriseReportDocument",
    "ReportPage",
    "SCHEMA_VERSION",
    "build_paginated_document",
]
