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

from backend.common.branding import CONFIDENTIALITY_BANNER, get_brand_service
from backend.executive_intelligence.constants import SAFETY_LOCKS
from backend.executive_intelligence.sanitizer import sanitize_payload
from backend.executive_intelligence.utils import as_mapping, utc_now_iso


CONFIDENTIALITY = CONFIDENTIALITY_BANNER


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
    brand = get_brand_service()
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
    .document-page {{ position:relative; isolation:isolate; min-height:250mm; }}
    {brand.watermark_css(page_selector=".document-page")}
  </style>
</head>
<body>
  <main class="document-page">
  {brand.watermark_markup()}
  <h1>{esc(brand.organization_name)} — Daily Executive Brief</h1>
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
  </main>
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
    return build_text_pdf(
        lines,
        watermark_text=get_brand_service().organization_name,
    )


def pdf_sha256(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()


def _pdf_lines(brief: Mapping[str, Any], *, printed_by: str, ts: str) -> list[str]:
    brand = get_brand_service()
    panels = as_mapping(brief.get("panels"))
    decision = as_mapping(panels.get("executive_decision"))
    market = as_mapping(panels.get("market_intelligence"))
    kpis = as_mapping(brief.get("executive_kpis"))
    actions = decision.get("executive_actions") or []
    lines = [
        f"{brand.organization_name} — Daily Executive Brief",
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


def build_text_pdf(
    lines: list[str],
    *,
    lines_per_page: int = 48,
    watermark_text: str | None = None,
) -> bytes:
    """Compatibility entry point delegated to the canonical PDF subsystem."""
    from backend.reporting.pdf.pdf_legacy_adapter import render_legacy_text_pdf

    # Branding is resolved exclusively by CSSBrandService in the canonical
    # renderer. The historical free-form watermark argument is intentionally
    # ignored to prevent direct branding injection.
    _ = watermark_text
    return render_legacy_text_pdf(lines, lines_per_page=lines_per_page)
