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
    route_crumb = f'<div class="mc-breadcrumb">Mission Control / {escape(active.label)}</div>'
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
    <input type="checkbox" id="mc-nav-toggle" class="mc-nav-toggle" aria-controls="mc-sidebar" aria-label="Open Mission Control navigation">
    <div class="mc-mobile-chrome">
      <button class="mc-back-btn" type="button" onclick="if (window.history.length > 1) window.history.go(-1)" aria-label="Back one screen">Back</button>
      <label class="mc-nav-toggle-btn" for="mc-nav-toggle">
        <span class="mc-nav-toggle-icon" aria-hidden="true"></span>
        <span class="mc-nav-toggle-text">Menu</span>
      </label>
      <div class="mc-mobile-chrome-copy">
        <strong>CSS Mission Control</strong>
        <span>{escape(active.label)}</span>
      </div>
    </div>
    <label class="mc-nav-backdrop" for="mc-nav-toggle" aria-hidden="true"></label>
    <aside class="mc-sidebar" id="mc-sidebar">
      <label class="mc-nav-close" for="mc-nav-toggle">Close</label>
      <div class="mc-brand">{brand}<span>Enterprise shell · Phase 177H</span></div>
      <nav class="mc-nav-home" aria-label="CSS Home">
        <a href="{escape(home_href)}" data-css-home="1">{_nav_icon()}<span class="mc-nav-label">Home</span></a>
      </nav>
      {nav}
      <form class="mc-logout-form" method="post" action="/logout">
        <button class="mc-logout-btn" type="submit">Log out / Exit</button>
      </form>
    </aside>
    <main class="mc-main">
      {_global_balance_bar(state_dict)}
      <header class="mc-topbar">
        <div>
          <strong>{escape(platform.get('product', 'CSS Mission Control'))}</strong>
          {route_crumb}
          {crumbs}
        </div>
        <div class="mc-status-strip" aria-label="Global status indicators">
          {_badge('Runtime', runtime_mode)}
          {_badge('Execution', execution_state)}
          {_broker_quick_control(state_dict)}
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




def _broker_quick_control(state_dict: Mapping[str, Any]) -> str:
    from dashboard.enterprise_shell.operator_configuration import broker_row_selectable

    brokers = _mapping(state_dict.get("brokers"))
    active = _mapping(brokers.get("active_broker"))
    selection = _mapping(brokers.get("operator_selection"))
    auth = _mapping(state_dict.get("authorization_context"))
    rows = brokers.get("broker_list") if isinstance(brokers.get("broker_list"), list) else []
    selected = str(
        selection.get("selected_broker")
        or active.get("selected_broker")
        or "NONE"
    ).strip().upper()
    selected_mode = str(selection.get("broker_mode") or active.get("broker_mode") or "PAPER").strip().upper()
    can_select = bool(auth.get("authenticated", True)) and bool(auth.get("active", True))

    options = []
    selectable_count = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        broker = str(row.get("broker") or "").strip().upper()
        if not broker or broker == "PAPER":
            continue
        available = broker_row_selectable(dict(row))
        if available:
            selectable_count += 1
        disabled = "" if available else " disabled"
        selected_attr = " selected" if broker == selected else ""
        state = str(row.get("operational_state") or row.get("status") or "UNAVAILABLE").replace("_", " ")
        label = broker + (" — Available" if available else " — Unavailable: " + state)
        options.append(
            '<option value="' + escape(broker) + '"' + disabled + selected_attr + '>'
            + escape(label) + '</option>'
        )

    if not can_select:
        return _badge("Broker", selected or "NONE")

    paper_selected = " selected" if selected_mode == "PAPER" else ""
    read_selected = " selected" if selected_mode == "LIVE_READ_ONLY" else ""
    submit_disabled = " disabled" if selectable_count == 0 else ""
    return (
        '<details class="mc-broker-quick" data-mc-status="broker">'
        '<summary class="mc-badge neutral"><span class="mc-badge-label">Broker</span>'
        '<span class="mc-badge-sep">: </span><span class="mc-badge-value">' + escape(selected or "NONE") + '</span>'
        '<span class="mc-broker-caret" aria-hidden="true"> ▾</span></summary>'
        '<div class="mc-broker-quick-popover">'
        '<form class="mc-broker-quick-form">'
        '<label>Preferred broker<select name="broker" required>' + ''.join(options) + '</select></label>'
        '<label>Mode<select name="broker_mode" required>'
        '<option value="PAPER"' + paper_selected + '>Paper</option>'
        '<option value="LIVE_READ_ONLY"' + read_selected + '>Live read-only</option></select></label>'
        '<label class="mc-confirm-choice"><input type="checkbox" name="confirm_choice" value="YES" required> Confirm broker choice</label>'
        '<button type="submit"' + submit_disabled + '>Use This Broker</button>'
        '</form><p class="mc-broker-quick-result" aria-live="polite"></p>'
        '<a href="/mission-control/broker-management">Open Broker Management</a>'
        '</div></details>'
        '<script>(function(){const forms=document.querySelectorAll(".mc-broker-quick-form");'
        'forms.forEach(form=>form.addEventListener("submit",async(ev)=>{ev.preventDefault();'
        'const out=form.parentElement.querySelector(".mc-broker-quick-result");'
        'const body=new URLSearchParams(new FormData(form));try{'
        'const response=await fetch("/operator-config/broker-selection",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/x-www-form-urlencoded","X-Requested-With":"XMLHttpRequest"},body});'
        'const data=await response.json();if(!response.ok)throw new Error(data.detail||"Save failed");'
        'out.textContent="Broker choice confirmed. Refreshing…";window.location.reload();'
        '}catch(err){out.textContent=String(err.message||err);}}));})();</script>'
    )



def _global_balance_bar(state_dict: Mapping[str, Any]) -> str:
    balances = _mapping(state_dict.get("broker_balance_summary"))
    summary = _mapping(balances.get("account_summary"))
    available = _mapping(summary.get("effective_available_balance")) or _mapping(summary.get("available_to_trade"))
    total = _mapping(summary.get("total_account_value"))
    pending_debits = _mapping(summary.get("pending_debits"))
    pending_credits = _mapping(summary.get("pending_credits"))
    context = _mapping(balances.get("account_context"))
    assets = balances.get("asset_breakdown") if isinstance(balances.get("asset_breakdown"), list) else []

    def amount(row: Mapping[str, Any]) -> str:
        if row.get("availability_state") != "AVAILABLE":
            return "UNAVAILABLE"
        value = row.get("value")
        currency = str(row.get("currency") or "").strip().upper()
        return f"{value} {currency}".strip()

    currency_parts = []
    for row in assets[:8]:
        if not isinstance(row, Mapping):
            continue
        currency = str(row.get("asset_currency") or row.get("currency") or "").strip().upper()
        value = row.get("available")
        if currency and value not in (None, ""):
            currency_parts.append(f"{escape(currency)} {escape(value)}")
    currency_text = " · ".join(currency_parts) if currency_parts else escape(context.get("base_currency") or available.get("currency") or "UNAVAILABLE")

    verification = available.get("verification_state") or "UNVERIFIED"
    return (
        '<section class="mc-global-balance" aria-label="Available account balances">'
        '<div class="mc-balance-main">'
        '<span class="mc-balance-label">Available Balance</span>'
        '<strong class="mc-sensitive-balance" data-balance-value="' + escape(amount(available)) + '">' + escape(amount(available)) + '</strong>'
        '<button class="mc-balance-eye" type="button" aria-pressed="false" aria-label="Mask balance" title="Mask / unmask balance">'
        '<span class="mc-eye-open" aria-hidden="true">◉</span><span class="mc-eye-closed" aria-hidden="true">◌</span></button>'
        '</div>'
        '<div class="mc-balance-meta">'
        '<span>Account value <b class="mc-sensitive-balance" data-balance-value="' + escape(amount(total)) + '">' + escape(amount(total)) + '</b></span>'
        '<span>Pending debits <b class="mc-sensitive-balance" data-balance-value="' + escape(amount(pending_debits)) + '">' + escape(amount(pending_debits)) + '</b></span>'
        '<span>Pending credits <b class="mc-sensitive-balance" data-balance-value="' + escape(amount(pending_credits)) + '">' + escape(amount(pending_credits)) + '</b></span>'
        '<span>Verification <b>' + escape(verification) + '</b></span>'
        '<span>Currencies <b class="mc-sensitive-balance" data-balance-value="' + escape(currency_text) + '">' + escape(currency_text) + '</b></span>'
        '</div>'
        '</section>'
        '<script>(function(){'
        "const key='css_balance_masked'; const btn=document.querySelector('.mc-balance-eye');"
        "const values=[...document.querySelectorAll('.mc-sensitive-balance')];"
        "if(!btn)return; function apply(masked){values.forEach(el=>{el.textContent=masked?'••••••':(el.dataset.balanceValue||'UNAVAILABLE');});"
        "btn.setAttribute('aria-pressed',masked?'true':'false');btn.setAttribute('aria-label',masked?'Unmask balance':'Mask balance');"
        "document.body.classList.toggle('mc-balance-masked',masked);try{localStorage.setItem(key,masked?'1':'0');}catch(e){}}"
        "let masked=false;try{masked=localStorage.getItem(key)==='1';}catch(e){} apply(masked);"
        "btn.addEventListener('click',()=>apply(!document.body.classList.contains('mc-balance-masked')));})();</script>"
    )



def _render_nav(active_key: str) -> str:
    links = []
    for section in MISSION_CONTROL_SECTIONS:
        current = ' aria-current="page"' if section.key == active_key else ""
        # Real same-origin path anchors — navigation must work with JavaScript disabled.
        links.append(
            f'<a href="{escape(section.route)}"{current} data-section="{escape(section.key)}">'
            f'{_nav_icon()}'
            f'<span class="mc-nav-label">{escape(section.label)}</span></a>'
        )
    return f'<nav class="mc-nav" aria-label="Mission Control navigation">{"".join(links)}</nav>'


def _nav_icon() -> str:
    return (
        '<span class="mc-nav-icon" aria-hidden="true">'
        '<svg viewBox="0 0 16 16" width="16" height="16" focusable="false">'
        '<circle cx="8" cy="8" r="3"></circle></svg></span>'
    )


def _badge(label: str, value: Any) -> str:
    text = "UNAVAILABLE" if value in (None, "") else str(value)
    key = "".join(ch.lower() if ch.isalnum() else "-" for ch in label).strip("-")
    lowered = text.lower()
    if any(token in lowered for token in ("unavailable", "disabled", "blocked")) or lowered == "red":
        tone = "bad"
    else:
        tone = status_class(text)
    return (
        f'<span class="mc-badge {tone}" data-mc-status="{escape(key)}">'
        f'<span class="mc-badge-label">{escape(label)}</span>'
        f'<span class="mc-badge-sep">: </span>'
        f'<span class="mc-badge-value">{escape(text)}</span>'
        "</span>"
    )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def escape(value: Any) -> str:
    return html.escape(str(value if value is not None else "UNAVAILABLE"), quote=True)


__all__ = ["render_mission_control_shell", "MC_NAV_TOUCH_DEBUG_JS"]
