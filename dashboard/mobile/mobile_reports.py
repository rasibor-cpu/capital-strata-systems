"""Mobile Reports Center pages (Phase 176A) — thin UI over ReportsCenterService."""

from __future__ import annotations

import html
import json
from typing import Any, Callable, Dict, Mapping, Optional

from backend.reports_center.rbac import ReportsAccessControl
from backend.reports_center.service import ReportsCenterService
from backend.reports_center.ui_contract import (
    category_sections,
    generatable_selector_options,
    navigation_payload,
)


def can_view_reports(user_ctx: Mapping[str, Any]) -> bool:
    role = str(user_ctx.get("role") or "VIEWER").upper()
    return ReportsAccessControl().can_view_catalog(role)


def can_generate_reports(user_ctx: Mapping[str, Any]) -> bool:
    role = str(user_ctx.get("role") or "VIEWER").upper()
    return ReportsAccessControl().can_generate(role, "reports_generate")


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _svc() -> ReportsCenterService:
    return ReportsCenterService()


def _role_user(user_ctx: Mapping[str, Any]) -> tuple[str, str]:
    return str(user_ctx.get("role") or "VIEWER").upper(), str(user_ctx.get("user_id") or "anonymous")


def render_reports_home(
    user_ctx: Mapping[str, Any],
    *,
    header_fn: Callable[..., str],
    page_fn: Callable[..., str],
    identity_fn: Callable[..., str],
    category: str | None = None,
) -> str:
    if not can_view_reports(user_ctx):
        return page_fn(
            "Reports",
            f"<main class='dashboard-shell'>{header_fn('Reports', user_ctx, 'reports')}"
            f"{identity_fn(user_ctx, 'Reports')}"
            "<section class='data-panel'><h2>Access denied</h2>"
            "<p>reports_view permission required.</p></section></main>",
        )
    role, _ = _role_user(user_ctx)
    home = _svc().home(role=role)
    auth = home.get("authorization") or {}
    cats = category_sections()
    if category:
        cats = [c for c in cats if c.get("key") == category]
    nav = "".join(
        f"<a class='button-link quiet' href='{_esc(n['href'])}'>{_esc(n['label'])}</a>"
        for n in navigation_payload(surface="mobile")
    )
    cat_markup = []
    for cat in cats:
        cards = "".join(_mobile_report_card(r) for r in (cat.get("reports") or [])[:40])
        cat_markup.append(
            f"""
<details class="rc-m-acc"{' open' if category else ''}>
  <summary>{_esc(cat.get('label'))} <span class="pill">{_esc(cat.get('count'))}</span></summary>
  <div class="rc-m-cards">{cards or '<p>No reports.</p>'}</div>
</details>
"""
        )
    recent = home.get("recent_reports") or []
    recent_cards = "".join(_archive_card(r) for r in recent[:8]) or "<p>No recent archived reports.</p>"
    latest = home.get("latest_daily_executive_brief") or {"status": "UNAVAILABLE"}
    body = f"""
<main class="dashboard-shell">
  {header_fn("Reports", user_ctx, "reports")}
  {identity_fn(user_ctx, "Institutional Reports")}
  <section class="system-strip" aria-label="Safety">
    <span>ADVISORY ONLY</span>
    <span>EXECUTION BLOCKED</span>
    <span>EMAIL DEFAULT: {_esc(home.get('email_policy_default'))}</span>
  </section>
  <section class="metric-grid" aria-label="Reports summary">
    <article><strong>Registered</strong><span>{_esc(home.get('total_registered'))}</span></article>
    <article><strong>Generatable</strong><span>{_esc(len(generatable_selector_options()))}</span></article>
    <article><strong>Failures</strong><span>{_esc((home.get('archive_health') or {}).get('failed_count'))}</span></article>
    <article><strong>reports_view</strong><span>{_esc(auth.get('reports_view'))}</span></article>
    <article><strong>reports_generate</strong><span>{_esc(auth.get('reports_generate'))}</span></article>
  </section>
  <section class="data-panel" aria-label="Reports navigation">
    <h2>Reports menu</h2>
    <div class="top-actions" style="flex-wrap:wrap;gap:8px;">{nav}</div>
  </section>
  <section class="data-panel" aria-label="Latest Daily Executive Brief">
    <h2>Latest Daily Executive Brief</h2>
    <pre class="terminal-panel" style="white-space:pre-wrap;overflow:auto;max-height:220px;">{_esc(json.dumps(latest, indent=2, default=str))}</pre>
  </section>
  <section class="data-panel" aria-label="Recent reports">
    <h2>Recent reports</h2>
    <div class="rc-m-cards">{recent_cards}</div>
  </section>
  <section class="data-panel" aria-label="Categories">
    <h2>Categories</h2>
    {''.join(cat_markup)}
  </section>
</main>
"""
    return page_fn("Reports", body)


def render_create(
    user_ctx: Mapping[str, Any],
    *,
    header_fn: Callable[..., str],
    page_fn: Callable[..., str],
    identity_fn: Callable[..., str],
    preselect: str = "",
    message: str = "",
    status: str = "info",
    result: Optional[dict] = None,
) -> str:
    if not can_view_reports(user_ctx):
        return page_fn("Create Report", "<main class='dashboard-shell'><p>Access denied.</p></main>")
    can_gen = can_generate_reports(user_ctx)
    options = generatable_selector_options()
    opts = "".join(
        f"<option value='{_esc(o['report_code'])}' {'selected' if o['report_code']==preselect else ''}>"
        f"{_esc(o['title'])} ({_esc(o['status'])})</option>"
        for o in options
    )
    # Embed filter field map for selected reports
    field_map = {o["report_code"]: o.get("filter_fields") or [] for o in options}
    disabled = "" if can_gen else "disabled"
    msg = f"<p class='status { 'error' if status=='error' else 'info' }'>{_esc(message)}</p>" if message else ""
    result_html = (
        f"<pre class='terminal-panel' style='white-space:pre-wrap;max-height:360px;overflow:auto;'>{_esc(json.dumps(result, indent=2, default=str))}</pre>"
        if result
        else ""
    )
    body = f"""
<main class="dashboard-shell">
  {header_fn("Create Report", user_ctx, "reports")}
  {identity_fn(user_ctx, "Create Report")}
  <section class="data-panel">
    <h2>Create Report</h2>
    <p>Registry-driven. Generation uses the canonical Reports Center service (server-side RBAC).</p>
    {msg}
    <form method="post" action="/reports/generate" class="form-panel" id="m-rc-form">
      <label>Report type
        <select name="report_code" id="m-rc-code" required {disabled}>
          <option value="">Select…</option>
          {opts}
        </select>
      </label>
      <div id="m-rc-filters"></div>
      <label>Limitations / notes (read-only)
        <textarea id="m-rc-limits" readonly rows="3"></textarea>
      </label>
      <button type="submit" {disabled}>Generate</button>
      <a class="button-link quiet" href="/reports">Back</a>
    </form>
    {result_html}
  </section>
  <script type="application/json" id="m-rc-fields">{html.escape(json.dumps(field_map))}</script>
  <script>
  (function(){{
    const map = JSON.parse(document.getElementById('m-rc-fields').textContent || '{{}}');
    const sel = document.getElementById('m-rc-code');
    const box = document.getElementById('m-rc-filters');
    const lim = document.getElementById('m-rc-limits');
    const gens = {json.dumps({o['report_code']: o.get('limitations') or '' for o in options})};
    function render(){{
      const code = sel.value;
      box.innerHTML = '';
      lim.value = gens[code] || '';
      (map[code] || []).forEach(function(f){{
        const label = document.createElement('label');
        label.textContent = f.label || f.name;
        let input;
        if (f.input === 'select') {{
          input = document.createElement('select');
          (f.options || []).forEach(function(opt){{
            const o = document.createElement('option'); o.value = opt; o.textContent = opt; input.appendChild(o);
          }});
        }} else {{
          input = document.createElement('input');
          input.type = f.input === 'date' ? 'date' : 'text';
        }}
        input.name = 'f_' + f.name;
        label.appendChild(input);
        box.appendChild(label);
      }});
    }}
    sel.addEventListener('change', render);
    if (sel.value) render();
  }})();
  </script>
</main>
"""
    return page_fn("Create Report", body)


def render_library(
    user_ctx: Mapping[str, Any],
    *,
    header_fn: Callable[..., str],
    page_fn: Callable[..., str],
    identity_fn: Callable[..., str],
    filters: Optional[dict] = None,
) -> str:
    if not can_view_reports(user_ctx):
        return page_fn("Report Library", "<main class='dashboard-shell'><p>Access denied.</p></main>")
    role, _ = _role_user(user_ctx)
    filters = filters or {}
    listing = _svc().list_library(filters=filters, role=role)
    reports = listing.get("reports") or []
    cards = "".join(_archive_card(r) for r in reports) or "<p>No reports found.</p>"
    body = f"""
<main class="dashboard-shell">
  {header_fn("Report Library", user_ctx, "reports")}
  {identity_fn(user_ctx, "Library")}
  <section class="data-panel">
    <h2>Report Library</h2>
    <form method="get" action="/reports/library" class="form-panel">
      <label>Report ID <input name="report_id" value="{_esc(filters.get('report_id'))}" autocomplete="off"></label>
      <label>Type <input name="report_type" value="{_esc(filters.get('report_type'))}"></label>
      <label>Status
        <select name="status">
          <option value="">Any</option>
          {''.join(f"<option value='{s}' {'selected' if filters.get('status')==s else ''}>{s}</option>" for s in ('FINAL','FAILED','DRAFT','SUPERSEDED'))}
        </select>
      </label>
      <label>Category <input name="category" value="{_esc(filters.get('category'))}"></label>
      <button type="submit">Filter</button>
    </form>
    <div class="rc-m-cards">{cards}</div>
  </section>
</main>
"""
    return page_fn("Report Library", body)


def render_detail(
    user_ctx: Mapping[str, Any],
    report_id: str,
    *,
    header_fn: Callable[..., str],
    page_fn: Callable[..., str],
    identity_fn: Callable[..., str],
) -> str:
    if not can_view_reports(user_ctx):
        return page_fn("Report Detail", "<main class='dashboard-shell'><p>Access denied.</p></main>")
    role, user_id = _role_user(user_ctx)
    result = _svc().retrieve(report_id, role=role)
    if result.get("status") != "OK":
        return page_fn(
            "Report Detail",
            f"<main class='dashboard-shell'>{header_fn('Report Detail', user_ctx, 'reports')}"
            f"<section class='data-panel'><h2>{_esc(result.get('status'))}</h2></section></main>",
        )
    report = result.get("report") or {}
    print_info = _svc().print_info(report_id, role=role, user_id=user_id)
    actions = []
    if print_info.get("status") == "OK":
        actions.append(f"<a class='button-link' href='/api/v1/reports/{_esc(report_id)}/print' target='_blank' rel='noopener'>Print preview</a>")
        actions.append(f"<a class='button-link quiet' href='/api/v1/reports/{_esc(report_id)}/pdf'>PDF info</a>")
    actions.append(f"<a class='button-link quiet' href='/reports/library'>Library</a>")
    content = report.get("html") or report.get("content") or report
    # Executive brief panels if present
    brief_extra = ""
    if isinstance(content, dict) and content.get("panels"):
        panels = content.get("panels") or {}
        kpis = content.get("kpis") or {}
        brief_extra = f"""
        <section class="data-panel"><h2>Executive panels</h2>
          <pre style="white-space:pre-wrap;max-height:280px;overflow:auto;">{_esc(json.dumps(panels, indent=2, default=str))}</pre>
        </section>
        <section class="data-panel"><h2>KPIs</h2>
          <pre style="white-space:pre-wrap;max-height:220px;overflow:auto;">{_esc(json.dumps(kpis, indent=2, default=str))}</pre>
        </section>
        """
    body = f"""
<main class="dashboard-shell">
  {header_fn("Report Detail", user_ctx, "reports")}
  {identity_fn(user_ctx, _esc(report.get('report_type') or report_id))}
  <section class="metric-grid">
    <article><strong>Status</strong><span>{_esc(report.get('report_status'))}</span></article>
    <article><strong>Version</strong><span>{_esc(report.get('report_version'))}</span></article>
    <article><strong>Date</strong><span>{_esc(report.get('report_date'))}</span></article>
    <article><strong>Official</strong><span>{_esc(report.get('official_report'))}</span></article>
    <article><strong>Advisory</strong><span>{_esc(report.get('advisory_only', True))}</span></article>
  </section>
  <section class="data-panel">
    <h2>{_esc(report.get('title') or report.get('report_type'))}</h2>
    <p><code>{_esc(report_id)}</code></p>
    <p>Hash: {_esc(report.get('report_hash'))}</p>
    <p>Limitations: {_esc(report.get('limitations') or '—')}</p>
    <div class="top-actions" style="flex-wrap:wrap;gap:8px;">{''.join(actions)}</div>
  </section>
  {brief_extra}
  <section class="data-panel"><h2>Content</h2>
    <pre style="white-space:pre-wrap;max-height:420px;overflow:auto;">{_esc(content if isinstance(content, str) else json.dumps(content, indent=2, default=str))}</pre>
  </section>
</main>
"""
    return page_fn("Report Detail", body)


def generate_from_form(user_ctx: Mapping[str, Any], form: Mapping[str, str]) -> dict[str, Any]:
    role, user_id = _role_user(user_ctx)
    report_code = str(form.get("report_code") or "").strip()
    filters: Dict[str, Any] = {}
    for key, value in form.items():
        if key.startswith("f_") and str(value).strip():
            filters[key[2:]] = str(value).strip()
    return _svc().generate(report_code, filters=filters, role=role, user_id=user_id, persist=True)


def _mobile_report_card(report: Mapping[str, Any]) -> str:
    code = _esc(report.get("report_code"))
    generatable = bool(report.get("generatable"))
    gen_link = (
        f"<a class='button-link' href='/reports/create?code={code}'>Generate</a>"
        if generatable
        else "<span class='pill'>Not generatable</span>"
    )
    return f"""
<article class="command-card" style="display:block;text-decoration:none;">
  <strong>{_esc(report.get('title'))}</strong>
  <span>{_esc(report.get('status'))} · {_esc(', '.join(report.get('supported_formats') or []))}</span>
  <span>{'OFFICIAL' if report.get('official_report') else 'ADVISORY'}</span>
  <span style="display:block;margin-top:6px;">{_esc((report.get('limitations') or '')[:160])}</span>
  <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">
    <a class="button-link quiet" href="/reports/create?code={code}">Open</a>
    {gen_link}
  </div>
</article>
"""


def _archive_card(report: Mapping[str, Any]) -> str:
    rid = _esc(report.get("report_id"))
    return f"""
<a class="command-card" href="/reports/detail/{rid}" style="display:block;text-decoration:none;">
  <strong>{_esc(report.get('report_type') or rid)}</strong>
  <span>{_esc(report.get('report_status'))} · {_esc(report.get('report_date'))} · {_esc(report.get('report_version'))}</span>
  <span>{_esc(rid)}</span>
</a>
"""
