from __future__ import annotations

import html
from collections.abc import Mapping
from typing import Any

from backend.security.authorization_context import ensure_mc_authorization_state
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS, section_for_key
from dashboard.mission_control.pages import render_page
from dashboard.mission_control.pages._components import status_class
from dashboard.mission_control.theme import MISSION_CONTROL_CSS
from dashboard.ui_interaction import DISCLOSURE_JS

# Phase 176H.1: DO NOT intercept touch with preventDefault. Native <a href>
# navigation must work without JavaScript. Optional diagnostics only.
MC_NAV_TOUCH_DEBUG_JS = r"""
(function () {
  if (!/[?&]touch_debug=1(?:&|$)/.test(String(window.location.search || ''))) return;
  var box = document.createElement('div');
  box.id = 'mc-touch-debug';
  box.setAttribute('aria-live', 'polite');
  box.style.cssText = 'position:fixed;left:8px;right:8px;bottom:8px;z-index:99999;max-height:42vh;overflow:auto;background:rgba(0,0,0,.92);color:#9fef9f;font:12px/1.35 monospace;padding:10px;border:1px solid #33c481;border-radius:8px;pointer-events:none;white-space:pre-wrap;';
  document.body.appendChild(box);
  function line(label, value) {
    return label + ': ' + (value == null ? 'null' : String(value));
  }
  function describe(el) {
    if (!el || !el.tagName) return String(el);
    var id = el.id ? ('#' + el.id) : '';
    var cls = el.className && typeof el.className === 'string' ? ('.' + el.className.trim().split(/\s+/).join('.')) : '';
    return el.tagName + id + cls;
  }
  function sample(ev, kind) {
    var t = ev.target;
    var node = t && t.nodeType === 3 ? t.parentElement : t;
    var x = 0, y = 0;
    if (ev.changedTouches && ev.changedTouches[0]) {
      x = ev.changedTouches[0].clientX;
      y = ev.changedTouches[0].clientY;
    } else if (typeof ev.clientX === 'number') {
      x = ev.clientX;
      y = ev.clientY;
    }
    var top = document.elementFromPoint(x, y);
    var a = node && node.closest ? node.closest('a[href]') : null;
    var cs = a ? window.getComputedStyle(a) : null;
    var br = a ? a.getBoundingClientRect() : null;
    box.textContent = [
      'CSS MC touch_debug=1 (dev only)',
      line('event', kind),
      line('target', describe(node)),
      line('defaultPrevented', ev.defaultPrevented),
      line('elementFromPoint', describe(top)),
      line('anchor', a ? a.getAttribute('href') : null),
      line('pointer-events', cs ? cs.pointerEvents : null),
      line('z-index', cs ? cs.zIndex : null),
      line('rect', br ? (Math.round(br.left) + ',' + Math.round(br.top) + ' ' + Math.round(br.width) + 'x' + Math.round(br.height)) : null),
      line('topmost', describe(top)),
      line('handler', 'none-native-anchor-only'),
      line('destination', a ? a.href : null)
    ].join('\n');
  }
  ['pointerdown', 'touchstart', 'touchend', 'click'].forEach(function (kind) {
    document.addEventListener(kind, function (ev) { sample(ev, kind); }, true);
  });
})();
"""


def render_mission_control_shell(
    state: Mapping[str, Any],
    *,
    active_section: str = "executive_overview",
    touch_debug: bool = False,
) -> str:
    from dashboard.enterprise_shell.routes import ROUTES, mobile_home_href
    from dashboard.enterprise_shell.shell import render_brand_home_link, render_breadcrumbs

    active = section_for_key(active_section)
    state_dict = ensure_mc_authorization_state(dict(state))
    platform = _mapping(state_dict.get("platform"))
    safety = _mapping(state_dict.get("safety"))
    runtime = _mapping(state_dict.get("runtime"))
    # Prefer canonical platform_status when contracts embed it (Phase 177F+).
    platform_status = _mapping(state_dict.get("platform_status")) or platform
    nav = _render_nav(active.key)
    body = render_page(active.key, state_dict)
    offline_banner = ""
    if platform.get("runtime_offline") or str(runtime.get("heartbeat_status", "")).upper() in {"STALE", "OFFLINE", "UNAVAILABLE", "UNKNOWN"}:
        offline_banner = (
            '<div class="mc-warning bad">'
            "Runtime evidence is unavailable or stale. Mission Control is displaying fail-closed read-only state."
            "</div>"
        )
    debug_script = f"<script>{MC_NAV_TOUCH_DEBUG_JS}</script>" if touch_debug else ""
    # Build marker proves served HTML includes Phase 176H.1 (native-anchor navigation).
    build_meta = '<meta name="css-mc-nav" content="native-anchor-176h1">'
    home_href = mobile_home_href(for_surface="mission_control")
    brand = render_brand_home_link(for_surface="mission_control", title="CSS Mission Control")
    crumbs = render_breadcrumbs(
        [
            ("Home", home_href),
            ("Mission Control", ROUTES.mc_home if active.key != "executive_overview" else None),
            (active.label, None),
        ]
    )
    runtime_mode = platform_status.get("runtime_mode") or platform.get("runtime_mode") or "DISABLED"
    execution_state = platform_status.get("execution_state") or (
        "BLOCKED" if safety.get("live_trading_blocked") else "UNKNOWN"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  {build_meta}
  <title>CSS Mission Control - {escape(active.label)}</title>
  <style>{MISSION_CONTROL_CSS}</style>
</head>
<body class="mc-body">
  <div class="mc-shell" data-mission-control-schema="{escape(state_dict.get('schema_version'))}" data-mc-nav="native-anchor-176h1">
    <aside class="mc-sidebar">
      <div class="mc-brand">{brand}<span>Enterprise shell · Phase 177H</span></div>
      <nav class="mc-nav-home" aria-label="CSS Home">
        <a href="{escape(home_href)}" data-css-home="1"><span class="mc-nav-icon" aria-hidden="true">home</span><span class="mc-nav-label">Home</span></a>
      </nav>
      {nav}
    </aside>
    <main class="mc-main">
      <header class="mc-topbar">
        <div>
          <strong>{escape(platform.get('product', 'CSS Mission Control'))}</strong>
          {crumbs}
        </div>
        <div class="mc-status-strip" aria-label="Global status indicators">
          {_badge('Runtime', runtime_mode)}
          {_badge('Execution', execution_state)}
          {_badge('Broker', platform_status.get('broker_mode') or platform.get('selected_broker') or 'NONE')}
          {_badge('Broker Health', platform.get('broker_health'))}
          {_badge('Platform', platform.get('platform_status'))}
          {_badge('Safety', safety.get('safety_status'))}
          {_badge('Posture', 'ADVISORY / READ-ONLY')}
        </div>
      </header>
      <section class="mc-content" aria-label="{escape(active.label)} workspace">
        {offline_banner}
        {body}
      </section>
      <footer class="mc-footer">
        Generated {escape(state_dict.get('generated_at'))}. Advisory-only display. No execution authority is granted from Mission Control.
      </footer>
    </main>
  </div>
  <script>{DISCLOSURE_JS}</script>
  {debug_script}
</body>
</html>"""


def _render_nav(active_key: str) -> str:
    links = []
    for section in MISSION_CONTROL_SECTIONS:
        current = ' aria-current="page"' if section.key == active_key else ""
        # Real same-origin path anchors — navigation must work with JavaScript disabled.
        links.append(
            f'<a href="{escape(section.route)}"{current} data-section="{escape(section.key)}">'
            f'<span class="mc-nav-icon" aria-hidden="true">{escape(section.icon)}</span>'
            f'<span class="mc-nav-label">{escape(section.label)}</span></a>'
        )
    return f'<nav class="mc-nav" aria-label="Mission Control navigation">{"".join(links)}</nav>'


def _badge(label: str, value: Any) -> str:
    text = "UNAVAILABLE" if value in (None, "") else str(value)
    return f'<span class="mc-badge {status_class(text)}">{escape(label)}: {escape(text)}</span>'


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def escape(value: Any) -> str:
    return html.escape(str(value if value is not None else "UNAVAILABLE"), quote=True)


__all__ = ["render_mission_control_shell", "MC_NAV_TOUCH_DEBUG_JS"]
