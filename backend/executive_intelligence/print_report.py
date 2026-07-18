"""Printable Daily Executive Brief — HTML + PDF (Phase 175).

Reuses report_printer sign-off conventions (Printed by / Generated).
Official printables only from immutable FINAL briefs.
"""

from __future__ import annotations

import hashlib
import html
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from backend.executive_intelligence.constants import SAFETY_LOCKS
from backend.executive_intelligence.sanitizer import sanitize_payload
from backend.executive_intelligence.utils import as_mapping, utc_now_iso


CONFIDENTIALITY = "CSS CONFIDENTIAL — ADVISORY ONLY — NOT AN EXECUTION ORDER"


def assert_final_printable(brief: Mapping[str, Any]) -> None:
    status = str(brief.get("report_status", "")).upper()
    if status != "FINAL":
        raise PermissionError(f"official_print_requires_final_status:{status or 'MISSING'}")
    if brief.get("advisory_only") is not True:
        raise PermissionError("official_print_requires_advisory_only")
    if brief.get("execution_allowed") is not False:
        raise PermissionError("official_print_requires_execution_blocked")


def render_printable_html(
    brief: Mapping[str, Any],
    *,
    printed_by: str,
    print_timestamp_utc: str | None = None,
) -> str:
    """Printer-friendly HTML for a FINAL brief."""
    assert_final_printable(brief)
    clean = sanitize_payload(dict(brief))
    ts = print_timestamp_utc or utc_now_iso()
    panels = as_mapping(clean.get("panels"))
    kpis = as_mapping(clean.get("executive_kpis"))
    decision = as_mapping(panels.get("executive_decision"))
    actions = decision.get("executive_actions") or decision.get("recommended_actions") or []
    market = as_mapping(panels.get("market_intelligence"))
    ops = as_mapping(panels.get("operational_health"))
    trading = as_mapping(panels.get("trading_intelligence"))
    learning = as_mapping(panels.get("learning"))

    def esc(value: Any) -> str:
        return html.escape(str(value if value is not None else "UNAVAILABLE"))

    action_rows = []
    if isinstance(actions, list):
        for idx, action in enumerate(actions[:5], start=1):
            if isinstance(action, Mapping):
                action_rows.append(
                    f"<li><strong>{esc(action.get('type'))}</strong> — {esc(action.get('title') or action.get('detail'))}</li>"
                )
            else:
                action_rows.append(f"<li>{esc(action)}</li>")
    if not action_rows:
        action_rows = ["<li>Monitor — No prioritized actions.</li>"]

    kpi_rows = []
    for name, kpi in kpis.items():
        if name == "aliases" or not isinstance(kpi, Mapping):
            continue
        kpi_rows.append(
            "<tr>"
            f"<td>{esc(name)}</td>"
            f"<td>{esc(kpi.get('value'))}</td>"
            f"<td>{esc(kpi.get('confidence'))}</td>"
            f"<td>{esc(kpi.get('freshness'))}</td>"
            f"<td>{esc(kpi.get('validation'))}</td>"
            f"<td>{esc(kpi.get('producer'))}</td>"
            "</tr>"
        )

    provenance = clean.get("provenance") if isinstance(clean.get("provenance"), list) else []
    prov_items = "".join(
        f"<li>{esc(as_mapping(p).get('source'))} · {esc(as_mapping(p).get('artifact_path'))} · "
        f"{esc(as_mapping(p).get('freshness'))}</li>"
        for p in provenance[:12]
    )

    unavailable = []
    for panel in panels.values():
        if isinstance(panel, Mapping):
            for field in panel.get("unavailable_fields") or []:
                unavailable.append(f"{panel.get('panel_id')}:{field}")
    unavailable_html = "".join(f"<li>{esc(u)}</li>" for u in unavailable) or "<li>None listed</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>CSS Daily Executive Brief — {esc(clean.get('report_date'))}</title>
  <style>
    @page {{ margin: 18mm; }}
    body {{ font-family: Georgia, "Times New Roman", serif; color: #111; margin: 24px; line-height: 1.35; }}
    h1,h2,h3 {{ font-family: Arial, Helvetica, sans-serif; }}
    .banner {{ border: 2px solid #8a1c1c; background: #fff5f5; padding: 10px 12px; margin-bottom: 16px; }}
    .meta {{ font-size: 12px; margin-bottom: 16px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 8px 0 16px; font-size: 12px; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f2f2f2; }}
    .footer {{ margin-top: 28px; border-top: 1px solid #999; padding-top: 10px; font-size: 11px; }}
    .page-break {{ page-break-before: always; }}
    .small {{ font-size: 11px; color: #333; }}
  </style>
</head>
<body>
  <h1>Capital Strata Systems — Daily Executive Brief</h1>
  <div class="banner">
    <strong>ADVISORY ONLY</strong> · execution_allowed=false · live_trading_blocked=true ·
    broker_execution_armed=false · {esc(CONFIDENTIALITY)}
  </div>
  <div class="meta">
    <div><strong>Report date:</strong> {esc(clean.get('report_date'))}</div>
    <div><strong>Report ID:</strong> {esc(clean.get('report_id'))}</div>
    <div><strong>Version:</strong> {esc(clean.get('report_version') or clean.get('version'))}</div>
    <div><strong>Generated (UTC):</strong> {esc(clean.get('generated_at_utc'))}</div>
    <div><strong>Reporting window:</strong> {esc(clean.get('reporting_window_start_utc') or clean.get('reporting_window_start'))}
      → {esc(clean.get('reporting_window_end_utc') or clean.get('reporting_window_end'))}</div>
    <div><strong>Validation:</strong> {esc(as_mapping(clean.get('validation')).get('validation_status') or clean.get('validation_status'))}</div>
    <div><strong>Overall status:</strong> {esc(clean.get('overall_status'))}</div>
    <div><strong>Report hash:</strong> <code>{esc(clean.get('report_hash'))}</code></div>
  </div>

  <h2>Highest Priority Today</h2>
  <ol>{''.join(action_rows)}</ol>

  <h2>Executive KPIs</h2>
  <table>
    <thead><tr><th>KPI</th><th>Value</th><th>Confidence</th><th>Freshness</th><th>Validation</th><th>Producer</th></tr></thead>
    <tbody>{''.join(kpi_rows)}</tbody>
  </table>

  <h2>Market Regime &amp; Confidence</h2>
  <ul>
    <li>Regime: {esc(market.get('regime_current'))}</li>
    <li>Prior regime: {esc(market.get('prior_regime'))}</li>
    <li>Market confidence: {esc(as_mapping(market.get('market_confidence')).get('value') or market.get('confidence'))}</li>
    <li>Panel status / freshness: {esc(market.get('panel_status'))} / {esc(market.get('freshness'))}</li>
  </ul>

  <h2>Five Executive Panels</h2>
  <table>
    <thead><tr><th>Panel</th><th>Status</th><th>Freshness</th></tr></thead>
    <tbody>
      <tr><td>Executive Decision</td><td>{esc(decision.get('panel_status'))}</td><td>{esc(decision.get('freshness'))}</td></tr>
      <tr><td>Operational Health</td><td>{esc(ops.get('panel_status'))}</td><td>{esc(ops.get('freshness'))}</td></tr>
      <tr><td>Market Intelligence</td><td>{esc(market.get('panel_status'))}</td><td>{esc(market.get('freshness'))}</td></tr>
      <tr><td>Trading Intelligence</td><td>{esc(trading.get('panel_status'))}</td><td>{esc(trading.get('freshness'))}</td></tr>
      <tr><td>Learning</td><td>{esc(learning.get('panel_status'))}</td><td>{esc(learning.get('freshness'))}</td></tr>
    </tbody>
  </table>

  <h2>Runtime / Broker / Portfolio / Risk Summaries</h2>
  <ul>
    <li>Runtime: {esc(as_mapping(ops.get('runtime_health')).get('status') or as_mapping(ops.get('runtime_health')).get('runtime_health'))}</li>
    <li>Broker: {esc(as_mapping(ops.get('broker_operational_status')).get('health'))}</li>
    <li>Portfolio health: {esc(trading.get('portfolio_health'))}</li>
    <li>Committee consensus: {esc(decision.get('committee_consensus'))}</li>
    <li>Learning: {esc(as_mapping(learning.get('learning_summary')).get('top_strategy') or learning.get('panel_status'))}</li>
  </ul>

  <h2>Source / Provenance Summary</h2>
  <ul>{prov_items or '<li>UNAVAILABLE</li>'}</ul>

  <h2>Unavailable-Data Warnings</h2>
  <ul>{unavailable_html}</ul>

  <div class="footer">
    <div>{esc(CONFIDENTIALITY)}</div>
    <div>Printed by: {esc(printed_by)}</div>
    <div>Print timestamp (UTC): {esc(ts)}</div>
    <div class="small">Page numbers applied by the browser/printer driver. CSS Daily Executive Brief — Phase 175 printable.</div>
    <div class="small">Safety locks: {esc(json.dumps(SAFETY_LOCKS))}</div>
  </div>
</body>
</html>
"""


def render_printable_pdf(
    brief: Mapping[str, Any],
    *,
    printed_by: str,
    print_timestamp_utc: str | None = None,
) -> bytes:
    """Generate a simple multi-page text PDF from a FINAL brief (no external PDF dependency)."""
    assert_final_printable(brief)
    clean = sanitize_payload(dict(brief))
    ts = print_timestamp_utc or utc_now_iso()
    lines = _pdf_lines(clean, printed_by=printed_by, ts=ts)
    return _build_simple_pdf(lines)


def pdf_sha256(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()


def _pdf_lines(brief: Mapping[str, Any], *, printed_by: str, ts: str) -> list[str]:
    panels = as_mapping(brief.get("panels"))
    decision = as_mapping(panels.get("executive_decision"))
    market = as_mapping(panels.get("market_intelligence"))
    kpis = as_mapping(brief.get("executive_kpis"))
    actions = decision.get("executive_actions") or []
    lines = [
        "Capital Strata Systems — Daily Executive Brief",
        CONFIDENTIALITY,
        f"Report date: {brief.get('report_date')}",
        f"Report ID: {brief.get('report_id')}",
        f"Version: {brief.get('report_version') or brief.get('version')}",
        f"Generated UTC: {brief.get('generated_at_utc')}",
        f"Window: {brief.get('reporting_window_start_utc')} -> {brief.get('reporting_window_end_utc')}",
        f"Validation: {as_mapping(brief.get('validation')).get('validation_status')}",
        f"Overall: {brief.get('overall_status')}",
        f"Report hash: {brief.get('report_hash')}",
        "ADVISORY ONLY | execution_allowed=false | live_trading_blocked=true | broker_execution_armed=false",
        "",
        "Highest Priority Today:",
    ]
    if isinstance(actions, list):
        for idx, action in enumerate(actions[:5], start=1):
            if isinstance(action, Mapping):
                lines.append(f"  {idx}. [{action.get('type')}] {action.get('title') or action.get('detail')}")
            else:
                lines.append(f"  {idx}. {action}")
    lines.append("")
    lines.append("Executive KPIs:")
    for name, kpi in kpis.items():
        if name == "aliases" or not isinstance(kpi, Mapping):
            continue
        lines.append(
            f"  - {name}: value={kpi.get('value')} conf={kpi.get('confidence')} "
            f"fresh={kpi.get('freshness')} val={kpi.get('validation')}"
        )
    lines.extend(
        [
            "",
            f"Market regime: {market.get('regime_current')} (prior={market.get('prior_regime')})",
            f"Market confidence: {as_mapping(market.get('market_confidence')).get('value') or market.get('confidence')}",
            "",
            f"Printed by: {printed_by}",
            f"Print timestamp UTC: {ts}",
        ]
    )
    return [str(line) for line in lines]


def _build_simple_pdf(lines: list[str], *, lines_per_page: int = 48) -> bytes:
    """Minimal PDF 1.4 writer (Helvetica text)."""
    pages: list[list[str]] = []
    for i in range(0, max(len(lines), 1), lines_per_page):
        pages.append(lines[i : i + lines_per_page])
    if not pages:
        pages = [["(empty)"]]

    objects: list[bytes] = []
    # 1: catalog, 2: pages tree — filled later
    objects.append(b"")  # placeholder index 0 unused
    objects.append(b"")  # 1 catalog
    objects.append(b"")  # 2 pages

    page_objs: list[int] = []
    content_objs: list[int] = []
    font_obj = 3
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    next_id = 4
    for page_index, page_lines in enumerate(pages):
        content = _page_content_stream(page_lines, page_no=page_index + 1, page_count=len(pages))
        content_id = next_id
        next_id += 1
        objects.append(f"<< /Length {len(content)} >>\nstream\n".encode("latin-1") + content + b"\nendstream")
        content_objs.append(content_id)

        page_id = next_id
        next_id += 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_obj} 0 R >> >> >>"
            ).encode("latin-1")
        )
        page_objs.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_objs)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_objs)} >>".encode("latin-1")
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"

    # Assemble xref
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i in range(1, len(objects)):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("latin-1"))
        out.extend(objects[i])
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects)}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for i in range(1, len(objects)):
        out.extend(f"{offsets[i]:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return bytes(out)


def _page_content_stream(lines: list[str], *, page_no: int, page_count: int) -> bytes:
    # PDF text: escape special chars
    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    y = 750
    parts = ["BT", "/F1 10 Tf", "14 TL", f"1 0 0 1 40 {y} Tm"]
    for line in lines:
        safe = esc(line[:110])
        parts.append(f"({safe}) Tj")
        parts.append("T*")
    footer = esc(f"Page {page_no} of {page_count} | {CONFIDENTIALITY}")
    parts.append(f"1 0 0 1 40 40 Tm ({footer}) Tj")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", errors="replace")
