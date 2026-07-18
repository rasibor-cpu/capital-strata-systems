"""Interactive Institutional Reports Center page (Phase 176A)."""

from __future__ import annotations

import html
import json
from typing import Any

from dashboard.mission_control.pages._components import page_header, warning_banner
from dashboard.ui_interaction import render_disclosure


def _json_script(element_id: str, payload: Any) -> str:
    """Embed JSON for browser JSON.parse without HTML-escaping quotes (which breaks parsing)."""
    raw = json.dumps(payload, default=str)
    # Prevent </script> breakout while keeping valid JSON text for textContent/JSON.parse.
    safe = raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f'<script type="application/json" id="{_esc(element_id)}">{safe}</script>'


def render(state: dict) -> str:
    """Render interactive Reports Center — catalogue-driven, RBAC-aware."""
    try:
        from backend.reports_center.service import ReportsCenterService
        from backend.reports_center.ui_contract import category_sections, generatable_selector_options
    except Exception as exc:
        return (
            page_header("Reports", "Institutional Reports Center")
            + warning_banner(f"Reports Center unavailable: {type(exc).__name__}", status="bad")
        )

    state = _with_canonical_auth(state)
    # Phase 176D: pages consume canonical authorization; they do not recompute RBAC.
    reports_auth = state.get("reports_authorization") if isinstance(state.get("reports_authorization"), dict) else None
    auth_ctx = state.get("authorization_context") if isinstance(state.get("authorization_context"), dict) else {}
    if reports_auth is None:
        return (
            page_header("Reports", "Institutional Reports Center")
            + warning_banner("Access denied: authorization context unavailable.", status="bad")
        )

    role = str(auth_ctx.get("role") or reports_auth.get("role") or "")
    user_id = str(auth_ctx.get("user_id") or reports_auth.get("user_id") or "")
    if not reports_auth.get("reports_view"):
        return (
            page_header("Reports", "Institutional Reports Center")
            + warning_banner("Access denied: reports_view permission required.", status="bad")
        )

    svc = ReportsCenterService()
    home = svc.home(role=role, user_id=user_id)
    # Prefer the precomputed canonical authorization payload for page/API parity.
    auth = dict(home.get("authorization") or {})
    auth.update({k: reports_auth.get(k) for k in reports_auth if k.startswith("reports_") or k in {
        "user_id", "role", "authenticated", "identity_source", "permission_source", "correlation_id",
        "executive_brief_email", "email_default_policy",
    }})
    home["authorization"] = auth
    can_generate = bool(auth.get("reports_generate"))
    categories = category_sections(role=role)
    generatable = generatable_selector_options(role=role)

    return (
        page_header(
            "Reports",
            "Canonical gateway for printable, downloadable, archived, and distributable CSS reports.",
        )
        + warning_banner(
            "Advisory-only Reports Center. Live trading blocked. Server-side RBAC mandatory.",
            status="warn",
        )
        + _metrics(home, auth)
        + _subnav()
        + _categories_panel(categories, can_generate)
        + _frequently_used(generatable, can_generate)
        + _create_panel(generatable, can_generate)
        + _library_panel(home)
        + _detail_panel()
        + _json_script("rc-catalog-data", {"categories": categories, "generatable": generatable})
        + _json_script(
            "rc-auth-data",
            {
                "role": role,
                "user_id": user_id,
                "can_generate": can_generate,
                "identity_source": auth_ctx.get("identity_source") or reports_auth.get("identity_source"),
                "authenticated": bool(auth_ctx.get("authenticated", reports_auth.get("authenticated"))),
            },
        )
        + _scripts()
    )


def _with_canonical_auth(state: dict) -> dict:
    from backend.security.authorization_context import ensure_mc_authorization_state

    return ensure_mc_authorization_state(state)


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _metrics(home: dict, auth: dict) -> str:
    items = [
        ("Registered", home.get("total_registered")),
        ("Archive recent", (home.get("archive_health") or {}).get("recent_count")),
        ("Failures", (home.get("archive_health") or {}).get("failed_count")),
        ("reports_view", auth.get("reports_view")),
        ("reports_generate", auth.get("reports_generate")),
        ("Email default", home.get("email_policy_default")),
    ]
    cards = "".join(
        f'<article class="mc-metric-card"><span>{_esc(k)}</span><strong>{_esc(v)}</strong></article>'
        for k, v in items
    )
    return f'<section class="mc-metric-grid" aria-label="Reports metrics">{cards}</section>'


def _subnav() -> str:
    links = [
        ("rc-categories", "Categories"),
        ("rc-frequent", "Generatable"),
        ("rc-create", "Create Report"),
        ("rc-library", "Library"),
        ("rc-detail", "Detail"),
    ]
    markup = "".join(
        f'<a class="rc-subnav-link" href="#{target}" data-css-subtab="{target}" role="tab">{_esc(label)}</a>'
        for target, label in links
    )
    return f'<nav class="rc-subnav" role="tablist" aria-label="Reports sections">{markup}</nav>'


def _categories_panel(categories: list[dict], can_generate: bool) -> str:
    blocks = []
    for cat in categories:
        key = str(cat.get("key") or "unknown")
        label = str(cat.get("label") or key)
        meta = f"{cat.get('count')} reports · {cat.get('available')} available"
        reports = cat.get("reports") or []
        cards = (
            f'<div class="rc-card-grid">{"".join(_report_card(r, can_generate) for r in reports)}</div>'
            if reports
            else "<p class='rc-muted'>No reports.</p>"
        )
        blocks.append(
            render_disclosure(
                title=label,
                body_html=cards,
                panel_id=f"cat-panel-{key}",
                anchor_id=f"cat-{key}",
                meta=meta,
                open_by_default=False,
                class_name="css-disclosure rc-category-disclosure",
            )
        )
    toolbar = """
<div class="css-disclosure-toolbar" role="toolbar" aria-label="Category expand controls">
  <button type="button" class="rc-btn" data-css-disclosure-expand-all="true">Expand all</button>
  <button type="button" class="rc-btn" data-css-disclosure-expand-all="false">Collapse all</button>
</div>
"""
    return (
        '<section class="mc-panel" id="rc-categories" data-css-disclosure-scope aria-label="Report categories">'
        "<h2>Report Categories</h2>"
        "<p class='rc-muted'>Expand a category to view registry entries. Generate is enabled only for AVAILABLE / AVAILABLE_WITH_LIMITATIONS when authorized.</p>"
        + toolbar
        + "".join(blocks)
        + "</section>"
    )


def _report_card(report: dict, can_generate: bool) -> str:
    code = _esc(report.get("report_code"))
    title = _esc(report.get("title"))
    status = _esc(report.get("status"))
    formats = _esc(", ".join(report.get("supported_formats") or []))
    official = "OFFICIAL" if report.get("official_report") else "ADVISORY"
    limitations = _esc(report.get("limitations") or "—")
    view_p = report.get("required_view_permission")
    gen_p = report.get("required_generate_permission")
    print_p = report.get("required_print_permission")
    # Display registry permission names; never invent defaults in the card.
    perms = _esc(
        f"View permission: {view_p}; Generate permission: {gen_p}; Print permission: {print_p}"
    )
    # Effective generate uses server-side can_generate when present; page-level
    # can_generate remains a coarse gate for the Create panel.
    effective = bool(report.get("can_generate")) if "can_generate" in report else (
        bool(report.get("generatable")) and can_generate
    )
    gen_state = _esc(report.get("generate_label") or ("Enabled" if effective else "Disabled"))
    blocked = report.get("generate_blocked_reason") or report.get("status") or ""
    reason_row = (
        f"<div><dt>Generate</dt><dd>{gen_state}</dd></div>"
        if effective
        else f"<div><dt>Generate</dt><dd>{gen_state} — reason: {_esc(blocked)}</dd></div>"
    )
    gen_disabled = "" if effective else " disabled"
    gen_label = "Generate" if effective else "Not generatable"
    return f"""
<article class="rc-card" data-report-code="{code}" data-generatable="{str(effective).lower()}">
  <header>
    <h3><button type="button" class="rc-linkish" data-rc-action="select" data-report-code="{code}">{title}</button></h3>
    <span class="rc-badge rc-status-{_esc(status).lower()}">{status}</span>
    <span class="rc-badge">{official}</span>
  </header>
  <dl class="rc-meta">
    <div><dt>Code</dt><dd><code>{code}</code></dd></div>
    <div><dt>Formats</dt><dd>{formats}</dd></div>
    <div><dt>Permissions</dt><dd>{perms}</dd></div>
    {reason_row}
    <div><dt>Limitations</dt><dd>{limitations}</dd></div>
  </dl>
  <div class="rc-actions">
    <button type="button" class="rc-btn" data-rc-action="view" data-report-code="{code}">View readiness</button>
    <button type="button" class="rc-btn rc-btn-primary" data-rc-action="generate-open" data-report-code="{code}"{gen_disabled}>{gen_label}</button>
  </div>
</article>
"""


def _frequently_used(generatable: list[dict], can_generate: bool) -> str:
    cards = "".join(_report_card(r, can_generate) for r in generatable[:12])
    return (
        '<section class="mc-panel" id="rc-frequent" aria-label="Frequently used reports">'
        "<h2>Frequently Used / Generatable</h2>"
        "<p class='rc-muted'>Click a title or View to inspect readiness. Generate opens Create Report with the code preselected.</p>"
        f'<div class="rc-card-grid">{cards}</div></section>'
    )


def _create_panel(generatable: list[dict], can_generate: bool) -> str:
    options = "".join(
        f'<option value="{_esc(g.get("report_code"))}">{_esc(g.get("title"))} ({_esc(g.get("status"))})</option>'
        for g in generatable
    )
    disabled = "" if can_generate else " disabled"
    return f"""
<section class="mc-panel" id="rc-create" aria-label="Create report">
  <h2>Create Report</h2>
  <p class="rc-muted">Registry-driven selector. Filters are limited to safe scopes. Generation uses POST /api/v1/reports/generate.</p>
  <form id="rc-create-form" class="rc-form" novalidate>
    <label class="rc-field">
      <span>Report type</span>
      <select id="rc-report-code" name="report_code" required{disabled}>
        <option value="">Select a report…</option>
        {options}
      </select>
    </label>
    <div id="rc-dynamic-filters" class="rc-filters" aria-live="polite"></div>
    <div id="rc-readiness" class="rc-readiness" aria-live="polite"></div>
    <div class="rc-actions">
      <button type="button" class="rc-btn" id="rc-check-readiness" data-rc-action="check-readiness" {disabled}>Check readiness</button>
      <button type="submit" class="rc-btn rc-btn-primary" id="rc-generate-btn"{disabled}>Generate</button>
    </div>
  </form>
  <pre id="rc-generate-result" class="rc-result" aria-live="polite" hidden></pre>
</section>
"""


def _library_panel(home: dict) -> str:
    recent = home.get("recent_reports") or []
    failed = home.get("report_generation_failures") or []
    latest = home.get("latest_daily_executive_brief") or {"status": "UNAVAILABLE"}
    recent_rows = "".join(
        f"""<tr>
          <td><button type="button" class="rc-linkish" data-rc-action="open-report" data-report-id="{_esc(r.get('report_id'))}">{_esc(r.get('report_id'))}</button></td>
          <td>{_esc(r.get('report_type'))}</td>
          <td>{_esc(r.get('report_status'))}</td>
          <td>{_esc(r.get('report_date'))}</td>
          <td>{_esc(r.get('report_version'))}</td>
        </tr>"""
        for r in recent[:20]
    ) or "<tr><td colspan='5'>No archived reports yet.</td></tr>"
    failed_rows = "".join(
        f"<tr><td>{_esc(r.get('report_id'))}</td><td>{_esc(r.get('report_type'))}</td><td>{_esc(r.get('report_status'))}</td></tr>"
        for r in failed[:10]
    ) or "<tr><td colspan='3'>None</td></tr>"
    return f"""
<section class="mc-panel" id="rc-library" aria-label="Report library">
  <h2>Report Library</h2>
  <div class="rc-library-tools">
    <label>Report ID <input type="search" id="rc-library-search" placeholder="cssrpt_…" autocomplete="off"></label>
    <button type="button" class="rc-btn" id="rc-library-open" data-rc-action="library-open">Open</button>
    <button type="button" class="rc-btn" id="rc-library-refresh" data-rc-action="library-refresh">Refresh list</button>
  </div>
  <h3>Latest Daily Executive Brief</h3>
  <pre class="rc-result">{_esc(json.dumps(latest, indent=2, default=str))}</pre>
  <h3>Recent reports</h3>
  <div class="rc-table-wrap"><table class="rc-table"><thead><tr><th>ID</th><th>Type</th><th>Status</th><th>Date</th><th>Version</th></tr></thead><tbody id="rc-library-body">{recent_rows}</tbody></table></div>
  <h3>Generation failures</h3>
  <div class="rc-table-wrap"><table class="rc-table"><thead><tr><th>ID</th><th>Type</th><th>Status</th></tr></thead><tbody>{failed_rows}</tbody></table></div>
</section>
"""


def _detail_panel() -> str:
    return """
<section class="mc-panel" id="rc-detail" aria-label="Report detail">
  <h2>Report Detail</h2>
  <p class="rc-muted">Select a library report or search by report ID.</p>
  <div class="rc-actions" id="rc-detail-actions" hidden>
    <button type="button" class="rc-btn" data-rc-detail="print">Print preview</button>
    <button type="button" class="rc-btn" data-rc-detail="pdf">PDF info</button>
    <button type="button" class="rc-btn" data-rc-detail="versions">Versions</button>
    <button type="button" class="rc-btn" data-rc-detail="audit">Audit</button>
    <button type="button" class="rc-btn" data-rc-detail="verify">Verify integrity</button>
    <a class="rc-btn" id="rc-detail-print-link" href="#" target="_blank" rel="noopener">Open printable HTML</a>
  </div>
  <pre id="rc-detail-body" class="rc-result" aria-live="polite">No report selected.</pre>
</section>
"""


def _scripts() -> str:
    # Category expand/collapse: shared CSSUIInteraction disclosures (Phase 176B).
    # Page script wires generate/readiness/library only.
    return r"""
<script>
(function () {
  const catalogEl = document.getElementById('rc-catalog-data');
  const authEl = document.getElementById('rc-auth-data');
  if (!catalogEl || !authEl) return;
  const catalog = JSON.parse(catalogEl.textContent || '{}');
  const auth = JSON.parse(authEl.textContent || '{}');
  const generatable = catalog.generatable || [];
  const byCode = {};
  generatable.forEach((r) => { byCode[r.report_code] = r; });
  (catalog.categories || []).forEach((c) => (c.reports || []).forEach((r) => { byCode[r.report_code] = r; }));

  const selectEl = document.getElementById('rc-report-code');
  const filtersEl = document.getElementById('rc-dynamic-filters');
  const readinessEl = document.getElementById('rc-readiness');
  const resultEl = document.getElementById('rc-generate-result');
  const detailBody = document.getElementById('rc-detail-body');
  const detailActions = document.getElementById('rc-detail-actions');
  const printLink = document.getElementById('rc-detail-print-link');
  let currentReportId = null;

  function headers() {
    return {
      'Content-Type': 'application/json',
      'X-CSS-Role': auth.role || 'VIEWER',
      'X-CSS-User-Id': auth.user_id || 'anonymous'
    };
  }

  function renderFilters(code) {
    const defn = byCode[code];
    filtersEl.innerHTML = '';
    if (!defn) return;
    (defn.filter_fields || []).forEach((field) => {
      const label = document.createElement('label');
      label.className = 'rc-field';
      const span = document.createElement('span');
      span.textContent = field.label || field.name;
      label.appendChild(span);
      let input;
      if (field.input === 'select') {
        input = document.createElement('select');
        (field.options || []).forEach((opt) => {
          const o = document.createElement('option');
          o.value = opt; o.textContent = opt; input.appendChild(o);
        });
      } else {
        input = document.createElement('input');
        input.type = field.input === 'date' ? 'date' : 'text';
        input.autocomplete = 'off';
        if (field.pattern) input.pattern = field.pattern;
      }
      input.name = field.name;
      input.id = 'rc-f-' + field.name;
      label.appendChild(input);
      filtersEl.appendChild(label);
    });
  }

  function collectFilters() {
    const filters = {};
    filtersEl.querySelectorAll('input,select').forEach((el) => {
      if (el.value) filters[el.name] = el.value;
    });
    return filters;
  }

  function selectReport(code) {
    if (!selectEl) return;
    selectEl.value = code;
    renderFilters(code);
    document.getElementById('rc-create')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async function loadReadiness(code) {
    readinessEl.textContent = 'Loading readiness…';
    try {
      const res = await fetch('/mission-control/api/reports/readiness/' + encodeURIComponent(code), { headers: headers() });
      const data = await res.json();
      readinessEl.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      readinessEl.textContent = 'Readiness request failed: ' + err;
    }
  }

  async function generate(code) {
    if (!auth.can_generate) {
      resultEl.hidden = false;
      resultEl.textContent = JSON.stringify({ status: 'DENIED', reason: 'reports_generate' }, null, 2);
      return;
    }
    resultEl.hidden = false;
    resultEl.textContent = 'Generating…';
    try {
      const res = await fetch('/api/v1/reports/generate', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ report_code: code, filters: collectFilters(), persist: true })
      });
      const data = await res.json();
      resultEl.textContent = JSON.stringify(data, null, 2);
      if (data.report_id) {
        currentReportId = data.report_id;
        await openReport(data.report_id);
      }
    } catch (err) {
      resultEl.textContent = 'Generate failed: ' + err;
    }
  }

  async function openReport(reportId) {
    currentReportId = reportId;
    detailActions.hidden = false;
    printLink.href = '/api/v1/reports/' + encodeURIComponent(reportId) + '/print';
    detailBody.textContent = 'Loading…';
    document.getElementById('rc-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    try {
      const res = await fetch('/mission-control/api/reports/' + encodeURIComponent(reportId), { headers: headers() });
      const data = await res.json();
      detailBody.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      detailBody.textContent = 'Detail failed: ' + err;
    }
  }

  async function detailAction(kind) {
    if (!currentReportId) return;
    const map = {
      print: '/mission-control/api/reports/' + encodeURIComponent(currentReportId) + '/print',
      pdf: '/mission-control/api/reports/' + encodeURIComponent(currentReportId) + '/pdf',
      versions: '/mission-control/api/reports/' + encodeURIComponent(currentReportId) + '/versions',
      audit: '/mission-control/api/reports/' + encodeURIComponent(currentReportId) + '/audit'
    };
    if (kind === 'verify') {
      try {
        const res = await fetch('/api/v1/reports/' + encodeURIComponent(currentReportId) + '/verify-integrity', {
          method: 'POST', headers: headers(), body: '{}'
        });
        detailBody.textContent = JSON.stringify(await res.json(), null, 2);
      } catch (err) {
        detailBody.textContent = 'Verify failed: ' + err;
      }
      return;
    }
    try {
      const res = await fetch(map[kind], { headers: headers() });
      detailBody.textContent = JSON.stringify(await res.json(), null, 2);
    } catch (err) {
      detailBody.textContent = 'Action failed: ' + err;
    }
  }

  document.addEventListener('click', (ev) => {
    const btn = ev.target.closest('[data-rc-action]');
    if (!btn) return;
    const action = btn.getAttribute('data-rc-action');
    const code = btn.getAttribute('data-report-code');
    const rid = btn.getAttribute('data-report-id');
    if (action === 'select' || action === 'generate-open') {
      if (code) { selectReport(code); if (action === 'generate-open') loadReadiness(code); }
    } else if (action === 'view' && code) {
      selectReport(code); loadReadiness(code);
    } else if (action === 'open-report' && rid) {
      openReport(rid);
    }
  });

  selectEl?.addEventListener('change', () => {
    renderFilters(selectEl.value);
    if (selectEl.value) loadReadiness(selectEl.value);
  });

  document.getElementById('rc-check-readiness')?.addEventListener('click', () => {
    if (selectEl?.value) loadReadiness(selectEl.value);
  });

  document.getElementById('rc-create-form')?.addEventListener('submit', (ev) => {
    ev.preventDefault();
    if (selectEl?.value) generate(selectEl.value);
  });

  document.getElementById('rc-library-open')?.addEventListener('click', () => {
    const q = document.getElementById('rc-library-search');
    if (q?.value) openReport(q.value.trim());
  });

  document.getElementById('rc-library-refresh')?.addEventListener('click', async () => {
    try {
      const res = await fetch('/mission-control/api/reports', { headers: headers() });
      const data = await res.json();
      const body = document.getElementById('rc-library-body');
      if (!body) return;
      const reports = data.reports || [];
      body.innerHTML = reports.slice(0, 20).map((r) =>
        '<tr><td><button type="button" class="rc-linkish" data-rc-action="open-report" data-report-id="' +
        String(r.report_id || '').replace(/"/g, '') + '">' + String(r.report_id || '') +
        '</button></td><td>' + String(r.report_type || '') + '</td><td>' + String(r.report_status || '') +
        '</td><td>' + String(r.report_date || '') + '</td><td>' + String(r.report_version || '') + '</td></tr>'
      ).join('') || '<tr><td colspan="5">No archived reports yet.</td></tr>';
    } catch (err) {
      detailBody.textContent = 'Library refresh failed: ' + err;
    }
  });

  detailActions?.querySelectorAll('[data-rc-detail]').forEach((btn) => {
    btn.addEventListener('click', () => detailAction(btn.getAttribute('data-rc-detail')));
  });

  if (window.CSSUIInteraction) window.CSSUIInteraction.init(document);

  // Deep-link: #rc-create?code=... or #cat-{category}
  const hash = window.location.hash || '';
  const match = hash.match(/code=([A-Za-z0-9_]+)/);
  if (match) selectReport(match[1]);
  if (window.CSSUIInteraction && typeof window.CSSUIInteraction.applyHash === 'function') {
    window.CSSUIInteraction.applyHash();
  }
})();
</script>
"""
