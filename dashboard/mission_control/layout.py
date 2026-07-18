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


def render_mission_control_shell(state: Mapping[str, Any], *, active_section: str = "executive_overview") -> str:
    active = section_for_key(active_section)
    state_dict = ensure_mc_authorization_state(dict(state))
    platform = _mapping(state_dict.get("platform"))
    safety = _mapping(state_dict.get("safety"))
    runtime = _mapping(state_dict.get("runtime"))
    nav = _render_nav(active.key)
    body = render_page(active.key, state_dict)
    offline_banner = ""
    if platform.get("runtime_offline") or str(runtime.get("heartbeat_status", "")).upper() in {"STALE", "OFFLINE", "UNAVAILABLE", "UNKNOWN"}:
        offline_banner = (
            '<div class="mc-warning bad">'
            "Runtime evidence is unavailable or stale. Mission Control is displaying fail-closed read-only state."
            "</div>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CSS Mission Control - {escape(active.label)}</title>
  <style>{MISSION_CONTROL_CSS}</style>
</head>
<body class="mc-body">
  <div class="mc-shell" data-mission-control-schema="{escape(state_dict.get('schema_version'))}">
    <aside class="mc-sidebar">
      <div class="mc-brand"><strong>CSS Mission Control</strong><span>Enterprise shell / MC-002</span></div>
      {nav}
    </aside>
    <main class="mc-main">
      <header class="mc-topbar">
        <div>
          <strong>{escape(platform.get('product', 'CSS Mission Control'))}</strong>
          <div class="mc-breadcrumb">Mission Control / {escape(active.label)}</div>
        </div>
        <div class="mc-status-strip" aria-label="Global status indicators">
          {_badge('Mode', platform.get('runtime_mode'))}
          {_badge('Broker', platform.get('selected_broker'))}
          {_badge('Broker Health', platform.get('broker_health'))}
          {_badge('Platform', platform.get('platform_status'))}
          {_badge('Execution', 'BLOCKED' if safety.get('live_trading_blocked') else 'UNKNOWN')}
          {_badge('Safety', safety.get('safety_status'))}
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
</body>
</html>"""


def _render_nav(active_key: str) -> str:
    links = []
    for section in MISSION_CONTROL_SECTIONS:
        current = ' aria-current="page"' if section.key == active_key else ""
        links.append(
            f'<a href="{escape(section.route)}"{current} data-section="{escape(section.key)}">'
            f'<span aria-hidden="true">{escape(section.icon)}</span><span>{escape(section.label)}</span></a>'
        )
    return f'<nav class="mc-nav" aria-label="Mission Control navigation">{"".join(links)}</nav>'


def _badge(label: str, value: Any) -> str:
    text = "UNAVAILABLE" if value in (None, "") else str(value)
    return f'<span class="mc-badge {status_class(text)}">{escape(label)}: {escape(text)}</span>'


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def escape(value: Any) -> str:
    return html.escape(str(value if value is not None else "UNAVAILABLE"), quote=True)


__all__ = ["render_mission_control_shell"]
