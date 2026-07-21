"""CSS Enterprise paginated report viewer (Phase 177H).

One page at a time by default — not a continuous scroll of the full document.
Consumes EnterpriseReportDocument / page dicts from the existing page_layout standard.
"""

from __future__ import annotations

import html
import json
from typing import Any, Mapping, Sequence

from backend.common.branding import get_brand_service
from dashboard.enterprise_shell.routes import ROUTES, mobile_home_href


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _pages_from_document(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    pages = document.get("pages") or []
    out: list[dict[str, Any]] = []
    for p in pages:
        if isinstance(p, Mapping):
            out.append(
                {
                    "page_number": int(p.get("page_number") or len(out) + 1),
                    "page_type": str(p.get("page_type") or "content"),
                    "title": str(p.get("title") or ""),
                    "lines": [str(x) for x in (p.get("lines") or [])],
                }
            )
    return out


def render_paginated_viewer(
    document: Mapping[str, Any],
    *,
    reports_href: str | None = None,
    home_href: str | None = None,
    print_href: str | None = None,
    export_pdf_href: str | None = None,
    surface: str = "mobile",
    title_override: str | None = None,
) -> str:
    """Render a full HTML document with page-oriented viewer controls."""
    brand = get_brand_service()
    pages = _pages_from_document(document)
    page_count = int(document.get("page_count") or len(pages) or 1)
    report_title = title_override or str(document.get("title") or "CSS Report")
    report_id = str(document.get("report_id") or "UNKNOWN")
    generated_at = str(document.get("generated_at") or "")
    css_version = str(document.get("css_version") or "")
    commit = document.get("commit_reference")
    presentation = dict(document.get("presentation") or {})
    branding = {
        **brand.document_context(
            report_title=report_title,
            generated_at=generated_at,
            document_id=report_id,
            runtime_version=css_version,
        ),
        **dict(document.get("branding") or {}),
    }
    home = home_href or mobile_home_href(for_surface=surface if surface != "mission_control" else "mission_control")
    reports = reports_href or (ROUTES.mc_reports if surface == "mission_control" else ROUTES.mobile_reports)

    # Build TOC from page titles
    toc_items = "".join(
        f'<li><button type="button" class="css-rv-toc-btn" data-page="{_esc(p["page_number"])}">'
        f'{_esc(p["page_number"])}. {_esc(p["title"])}</button></li>'
        for p in pages
    )

    page_sheets = []
    for p in pages:
        body = _esc("\n".join(p["lines"])).replace("\n", "<br>")
        heading = "h1" if p["page_type"] == "cover" else "h2"
        page_sheets.append(
            f'<article class="css-rv-page" data-page="{_esc(p["page_number"])}" hidden '
            f'aria-label="Page {_esc(p["page_number"])} of {_esc(page_count)}">'
            f"{brand.watermark_markup()}"
            '<header class="css-rv-document-header">'
            f"{_esc(branding['organization'])} · {_esc(report_title)} · "
            f"{_esc(generated_at)} · {_esc(branding['classification'])}</header>"
            f'<{heading}>{_esc(p["title"])}</{heading}>'
            f'<div class="css-rv-meta">Report ID: {_esc(report_id)} · Generated: {_esc(generated_at)}'
            f' · CSS: {_esc(css_version)}'
            + (f' · Commit: {_esc(commit)}' if commit else "")
            + "</div>"
            f'<div class="css-rv-body">{body}</div>'
            f'<footer class="css-rv-page-footer">Page {_esc(p["page_number"])} of {_esc(page_count)}'
            f" · Document {_esc(report_id)} · Runtime {_esc(css_version)}"
            f" · {_esc(branding['confidentiality_banner'])}</footer>"
            "</article>"
        )

    options = "".join(
        f'<option value="{_esc(p["page_number"])}">Page {_esc(p["page_number"])}</option>'
        for p in pages
    ) or '<option value="1">Page 1</option>'

    print_btn = (
        f'<a class="css-rv-btn" href="{_esc(print_href)}" target="_blank" rel="noopener">Print</a>'
        if print_href
        else '<button type="button" class="css-rv-btn" data-rv-print="1">Print</button>'
    )
    pdf_btn = (
        f'<a class="css-rv-btn" href="{_esc(export_pdf_href)}" target="_blank" rel="noopener">Export PDF</a>'
        if export_pdf_href
        else ""
    )

    pages_json = json.dumps([p["page_number"] for p in pages])
    continuous = bool(presentation.get("viewer_hints", {}).get("continuous_scroll_default"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{_esc(report_title)} — {_esc(brand.short_application_name)} Report Viewer</title>
  <style>{_viewer_css()}</style>
</head>
<body class="css-rv-body-root" data-continuous-default="{str(continuous).lower()}">
  <a class="css-rv-skip" href="#css-rv-stage">Skip to report page</a>
  <header class="css-rv-toolbar" role="banner">
    <div class="css-rv-toolbar-left">
      <a class="css-rv-brand" href="{_esc(home)}" aria-label="CSS Home"><img src="{_esc(brand.asset_url('logo'))}" alt="" aria-hidden="true"><span>CSS</span></a>
      <a class="css-rv-btn" href="{_esc(home)}">Home</a>
      <a class="css-rv-btn" href="{_esc(reports)}">Back to Reports</a>
    </div>
    <div class="css-rv-toolbar-center" role="group" aria-label="Page navigation">
      <button type="button" class="css-rv-btn" id="css-rv-prev" aria-label="Previous page">Previous</button>
      <label class="css-rv-page-label">
        <span class="visually-hidden">Page selector</span>
        <select id="css-rv-selector" aria-label="Select page">{options}</select>
      </label>
      <span id="css-rv-indicator" aria-live="polite">1 / {_esc(page_count)}</span>
      <button type="button" class="css-rv-btn" id="css-rv-next" aria-label="Next page">Next</button>
    </div>
    <div class="css-rv-toolbar-right">
      <button type="button" class="css-rv-btn" id="css-rv-toc-toggle" aria-expanded="false" aria-controls="css-rv-toc">Table of Contents</button>
      {print_btn}
      {pdf_btn}
      <button type="button" class="css-rv-btn" id="css-rv-fit" aria-pressed="false">Fit width</button>
      <button type="button" class="css-rv-btn" id="css-rv-readable" aria-pressed="false">Readable text</button>
    </div>
  </header>
  <div class="css-rv-layout">
    <aside id="css-rv-toc" class="css-rv-toc" hidden aria-label="Table of Contents">
      <h2>Contents</h2>
      <ol>{toc_items}</ol>
    </aside>
    <main id="css-rv-stage" class="css-rv-stage" tabindex="-1" aria-label="{_esc(report_title)}">
      {"".join(page_sheets) if page_sheets else '<article class="css-rv-page" data-page="1"><p>No pages available.</p></article>'}
    </main>
  </div>
  <script>
  (function () {{
    var pages = {pages_json};
    var idx = 0;
    var stage = document.getElementById('css-rv-stage');
    var selector = document.getElementById('css-rv-selector');
    var indicator = document.getElementById('css-rv-indicator');
    var toc = document.getElementById('css-rv-toc');
    var tocToggle = document.getElementById('css-rv-toc-toggle');
    function show(i) {{
      if (!pages.length) return;
      idx = Math.max(0, Math.min(i, pages.length - 1));
      var num = pages[idx];
      var nodes = stage.querySelectorAll('.css-rv-page');
      for (var n = 0; n < nodes.length; n++) {{
        var on = String(nodes[n].getAttribute('data-page')) === String(num);
        nodes[n].hidden = !on;
        if (on) nodes[n].setAttribute('aria-hidden', 'false');
        else nodes[n].setAttribute('aria-hidden', 'true');
      }}
      if (selector) selector.value = String(num);
      if (indicator) indicator.textContent = (idx + 1) + ' / ' + pages.length;
      document.title = {_esc_js(report_title)} + ' — page ' + (idx + 1);
      try {{ history.replaceState(null, '', '#page=' + num); }} catch (e) {{}}
    }}
    function fromHash() {{
      var m = /[#&]page=(\\d+)/.exec(location.hash || '');
      if (!m) return 0;
      var want = parseInt(m[1], 10);
      for (var i = 0; i < pages.length; i++) if (pages[i] === want) return i;
      return 0;
    }}
    document.getElementById('css-rv-prev').addEventListener('click', function () {{ show(idx - 1); }});
    document.getElementById('css-rv-next').addEventListener('click', function () {{ show(idx + 1); }});
    if (selector) selector.addEventListener('change', function () {{
      var want = parseInt(selector.value, 10);
      for (var i = 0; i < pages.length; i++) if (pages[i] === want) {{ show(i); break; }}
    }});
    if (tocToggle) tocToggle.addEventListener('click', function () {{
      var open = toc.hasAttribute('hidden');
      if (open) toc.removeAttribute('hidden'); else toc.setAttribute('hidden', '');
      tocToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }});
    document.querySelectorAll('.css-rv-toc-btn').forEach(function (btn) {{
      btn.addEventListener('click', function () {{
        var want = parseInt(btn.getAttribute('data-page'), 10);
        for (var i = 0; i < pages.length; i++) if (pages[i] === want) {{ show(i); break; }}
      }});
    }});
    var printBtn = document.querySelector('[data-rv-print]');
    if (printBtn) printBtn.addEventListener('click', function () {{ window.print(); }});
    document.getElementById('css-rv-fit').addEventListener('click', function () {{
      document.body.classList.toggle('css-rv-fit-width');
      this.setAttribute('aria-pressed', document.body.classList.contains('css-rv-fit-width') ? 'true' : 'false');
    }});
    document.getElementById('css-rv-readable').addEventListener('click', function () {{
      document.body.classList.toggle('css-rv-readable');
      this.setAttribute('aria-pressed', document.body.classList.contains('css-rv-readable') ? 'true' : 'false');
    }});
    // Swipe between pages on touch devices
    var sx = 0;
    stage.addEventListener('touchstart', function (ev) {{
      if (ev.changedTouches && ev.changedTouches[0]) sx = ev.changedTouches[0].clientX;
    }}, {{ passive: true }});
    stage.addEventListener('touchend', function (ev) {{
      if (!ev.changedTouches || !ev.changedTouches[0]) return;
      var dx = ev.changedTouches[0].clientX - sx;
      if (Math.abs(dx) < 56) return;
      if (dx < 0) show(idx + 1); else show(idx - 1);
    }}, {{ passive: true }});
    document.addEventListener('keydown', function (ev) {{
      if (ev.key === 'ArrowRight' || ev.key === 'PageDown') {{ ev.preventDefault(); show(idx + 1); }}
      if (ev.key === 'ArrowLeft' || ev.key === 'PageUp') {{ ev.preventDefault(); show(idx - 1); }}
    }});
    show(fromHash());
  }})();
  </script>
</body>
</html>"""


def _esc_js(value: str) -> str:
    return json.dumps(str(value))


def _viewer_css() -> str:
    brand = get_brand_service()
    css = """
:root { --rv-ink:__BRAND_INK__; --rv-muted:#5a6b75; --rv-bg:#d8dee3; --rv-sheet:#fff; --rv-accent:__BRAND_GOLD__; }
* { box-sizing: border-box; }
body.css-rv-body-root { margin:0; font-family: Georgia, "Times New Roman", serif; background:var(--rv-bg); color:var(--rv-ink); }
.css-rv-skip { position:absolute; left:-9999px; }
.css-rv-skip:focus { left:8px; top:8px; background:#fff; padding:8px; z-index:99; }
.css-rv-toolbar {
  position:sticky; top:0; z-index:20; display:flex; flex-wrap:wrap; gap:8px; align-items:center;
  justify-content:space-between; padding:10px 12px; padding-bottom:max(10px, env(safe-area-inset-bottom));
  background:#10202a; color:#fff; font-family:"Segoe UI", Arial, sans-serif;
}
.css-rv-toolbar a, .css-rv-btn {
  display:inline-flex; align-items:center; justify-content:center; min-height:44px; min-width:44px;
  padding:8px 12px; border-radius:8px; border:1px solid rgba(255,255,255,.25); background:transparent;
  color:#fff; text-decoration:none; font-size:14px; cursor:pointer;
}
.css-rv-btn:focus-visible, .css-rv-toolbar a:focus-visible { outline:2px solid #68a8ff; outline-offset:2px; }
.css-rv-brand { font-weight:800; letter-spacing:.04em; gap:8px; }
.css-rv-brand img { width:28px; height:28px; border-radius:6px; }
.css-rv-toolbar-center { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.css-rv-toolbar-right, .css-rv-toolbar-left { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.css-rv-page-label select { min-height:44px; font-size:14px; }
.css-rv-layout { display:grid; grid-template-columns:1fr; gap:0; }
.css-rv-toc { background:#f4f7f8; border-right:1px solid #c8d2d8; padding:16px; max-height:40vh; overflow:auto; font-family:"Segoe UI", Arial, sans-serif; }
.css-rv-toc ol { margin:0; padding-left:18px; }
.css-rv-toc-btn { background:none; border:none; color:#146767; text-align:left; cursor:pointer; padding:8px 4px; min-height:40px; width:100%; }
.css-rv-stage { padding:16px; display:flex; justify-content:center; min-height:70vh; }
.css-rv-page {
  background:var(--rv-sheet); width:min(210mm, 100%); min-height:297mm; padding:18mm;
  box-shadow:0 4px 18px rgba(0,0,0,.18); border:1px solid #b8c2c8; margin:0 auto;
}
.css-rv-page h1 { font-size:22pt; margin:0 0 12px; }
.css-rv-page h2 { font-size:14pt; margin:0 0 10px; }
.css-rv-document-header { font-size:9pt; color:#555; border-bottom:1px solid #ddd; padding-bottom:6px; margin-bottom:12px; }
.css-rv-meta { color:var(--rv-muted); font-size:10pt; margin-bottom:16px; font-family:"Segoe UI", Arial, sans-serif; }
.css-rv-body { font-size:11pt; line-height:1.45; white-space:pre-wrap; word-break:break-word; }
.css-rv-page-footer { margin-top:24px; padding-top:8px; border-top:1px solid #ccc; font-size:9pt; color:#666; font-family:"Segoe UI", Arial, sans-serif; }
.visually-hidden { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); }
body.css-rv-fit-width .css-rv-page { width:100%; min-height:auto; padding:16px; }
body.css-rv-readable .css-rv-body { font-size:16px; line-height:1.6; }
@media (min-width:900px) {
  .css-rv-layout:has(#css-rv-toc:not([hidden])) { grid-template-columns:260px 1fr; }
  .css-rv-toc { max-height:none; position:sticky; top:64px; height:calc(100vh - 64px); }
}
@media (max-width:700px) {
  .css-rv-page { width:100%; min-height:auto; padding:16px; box-shadow:none; }
  .css-rv-toolbar-center { order:3; width:100%; justify-content:center; }
}
@media print {
  .css-rv-toolbar, .css-rv-toc { display:none !important; }
  .css-rv-page { display:block !important; box-shadow:none; border:none; page-break-after:always; width:auto; min-height:auto; }
  .css-rv-page[hidden] { display:block !important; }
}
"""
    return (
        css.replace("__BRAND_INK__", brand.palette.ink)
        .replace("__BRAND_GOLD__", brand.palette.gold)
        + brand.watermark_css(page_selector=".css-rv-page")
    )


def document_from_pages(
    *,
    title: str,
    report_id: str,
    pages: Sequence[Mapping[str, Any]],
    generated_at: str = "",
    css_version: str = "",
    commit_reference: str | None = None,
    presentation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    page_list = list(pages)
    brand = get_brand_service()
    return {
        "title": title,
        "report_id": report_id,
        "css_version": css_version,
        "commit_reference": commit_reference,
        "generated_at": generated_at,
        "page_count": len(page_list),
        "pages": [dict(p) for p in page_list],
        "presentation": dict(presentation or {"page_size": "A4", "viewer_hints": {"continuous_scroll_default": False}}),
        "branding": brand.document_context(
            report_title=title,
            generated_at=generated_at,
            document_id=report_id,
            runtime_version=css_version,
        ),
    }


__all__ = ["document_from_pages", "render_paginated_viewer"]
