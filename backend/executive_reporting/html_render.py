"""Phase 178 — HTML rendering for executive financial reports."""

from __future__ import annotations

import html
from typing import Any


def _esc(value: Any) -> str:
    if value is None:
        return "—"
    text = str(value)
    if text.strip().upper() in {"NONE", "NULL", "UNDEFINED", "NAN"}:
        return "—"
    return html.escape(text)


def render_executive_financial_html(package: dict[str, Any]) -> str:
    """Clear executive HTML with required headings. Advisory banner included."""
    summary = package.get("financial_summary") if isinstance(package.get("financial_summary"), dict) else {}
    narrative = package.get("narrative") if isinstance(package.get("narrative"), dict) else {}
    sections = narrative.get("sections") if isinstance(narrative.get("sections"), dict) else {}
    actions = package.get("management_actions") if isinstance(package.get("management_actions"), list) else []
    run = package.get("profitability_run_rate") if isinstance(package.get("profitability_run_rate"), dict) else {}
    period = package.get("reporting_period") if isinstance(package.get("reporting_period"), dict) else {}

    action_items = "".join(
        f"<li><strong>{_esc(a.get('action'))}</strong> — {_esc(a.get('reason'))}</li>"
        for a in actions
        if isinstance(a, dict)
    ) or "<li>None generated from current conditions.</li>"

    def section_html(title: str, body: str) -> str:
        return f"<h2>{html.escape(title)}</h2><p>{_esc(body)}</p>"

    kpi_rows = "".join(
        f"<tr><th>{_esc(r.get('kpi'))}</th><td>{_esc(r.get('value'))}</td></tr>"
        for r in (package.get("kpi_table") or [])
        if isinstance(r, dict)
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Executive Financial Report</title></head>
<body>
<div style="border:2px solid #b45309;padding:8px;margin-bottom:12px;">
ADVISORY ONLY — management report. Not audited statutory financial statements.
No trading or execution authority. trading_impact=false.
</div>
<h1>Executive Financial Report</h1>
<p>Period: {_esc(period.get('label'))} | Currency: {_esc(package.get('currency'))} |
Generated: {_esc(package.get('generated_at'))}</p>

{section_html('Executive Summary', sections.get('executive_conclusion') or '')}

<h2>Financial Performance</h2>
<table>{kpi_rows}</table>
<p>{_esc(sections.get('profitability'))}</p>
<p>{_esc(sections.get('revenue_drivers'))}</p>
<p>{_esc(sections.get('cost_drivers'))}</p>

<h2>Profitability Target and Required Run Rate</h2>
<p>{_esc(sections.get('target_progress'))}</p>
<table>
<tr><th>Traffic Light</th><td>{_esc(summary.get('profitability_traffic_light') or run.get('traffic_light'))}</td></tr>
<tr><th>Required Daily Run Rate</th><td>{_esc(summary.get('required_daily_run_rate'))}</td></tr>
<tr><th>Projected Period-End Profit</th><td>{_esc(summary.get('projected_period_end_profit'))}</td></tr>
<tr><th>Projected Target Variance</th><td>{_esc(summary.get('projected_target_variance'))}</td></tr>
</table>

<h2>Income Statement</h2>
<pre>{_esc(package.get('income_statement'))}</pre>

<h2>Balance Sheet</h2>
<pre>{_esc(package.get('balance_sheet'))}</pre>
<p>{_esc(sections.get('balance_sheet_position'))}</p>

<h2>Cash Flow</h2>
<pre>{_esc(package.get('cash_flow_statement'))}</pre>
<p>{_esc(sections.get('cash_position'))}</p>

<h2>Key Risks and Data Limitations</h2>
<p>{_esc(sections.get('data_quality_issues'))}</p>
<ul>
{''.join(f'<li>{_esc(x)}</li>' for x in (package.get('limitations') or []))}
{''.join(f'<li>Warning: {_esc(w)}</li>' for w in (package.get('warnings') or [])[:12])}
{''.join(f'<li>Blocker: {_esc(b)}</li>' for b in (package.get('blockers') or [])[:12])}
</ul>

<h2>Management Actions</h2>
<ul>{action_items}</ul>

<p><em>Report ID {_esc(package.get('report_id'))} · schema {_esc(package.get('schema_version'))}</em></p>
</body></html>"""
