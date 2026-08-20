"""Rendered neutral CSS mobile landing page."""

from __future__ import annotations

import html
from typing import Any, Mapping

from backend.common.branding import get_brand_service


def render_mobile_landing(
    navigation: Mapping[str, Any],
    *,
    manifest_href: str,
    title: str = "CSS Mobile Launcher",
    balance_summary: Mapping[str, Any] | None = None,
    operator_summary: Mapping[str, Any] | None = None,
    extra_head: str = "",
    service_worker_script: str = "",
) -> str:
    brand = get_brand_service()
    pwa_head = extra_head or brand.html_head(
        manifest_href=manifest_href,
        include_manifest=False,
        include_viewport=False,
        application_name=title,
    )
    destinations = [
        item
        for item in navigation.get("landing", [])
        if isinstance(item, Mapping)
        and item.get("enabled", True)
        and item.get("href")
        and "/api/" not in str(item.get("href") or "")
    ]
    links = "".join(
        '<a class="landing-link" href="{href}" aria-label="{aria}">{label}</a>'.format(
            href=_esc(item["href"]),
            aria=_esc(item.get("aria_label") or item["label"]),
            label=_esc(item["label"]),
        )
        for item in destinations
    )
    balance = dict(balance_summary or {})
    balance_fields = (
        balance.get("account_summary")
        if isinstance(balance.get("account_summary"), Mapping)
        else {}
    )
    account_value = (
        balance_fields.get("total_account_value")
        if isinstance(balance_fields.get("total_account_value"), Mapping)
        else {}
    )
    account_value_state = str(
        account_value.get("availability_state") or "UNAVAILABLE"
    ).strip().upper()

    account_value_currency = str(
        account_value.get("currency") or ""
    ).strip()

    if account_value_state == "AVAILABLE":
        account_value_display = str(account_value.get("value"))

        if (
            account_value_currency
            and account_value_currency.upper()
            not in {"UNAVAILABLE", "UNKNOWN", "N/A", "NONE"}
        ):
            account_value_display = (
                f"{account_value_display} {account_value_currency}"
            )
    else:
        account_value_display = "UNAVAILABLE"

    balance_html = (
        '<section class="balance" aria-label="Account balance summary">'
        "<strong>Account value</strong>"
        f"<span>{_esc(account_value_display)}</span>"
        f"<small>{_esc(account_value_state)} · "
        f"{_esc(account_value.get('provenance') or 'UNAVAILABLE')}</small>"
        "</section>"
    )

    operator = dict(operator_summary or {})

    session_cycle = operator.get("session_cycle")
    if session_cycle is None:
        session_cycle = operator.get("current_cycle")

    current_log_on = _format_operator_time(
        operator.get("current_log_on")
        or operator.get("last_auth_time")
    )

    last_log_on = _format_operator_time(
        operator.get("last_log_on")
    )

    operator_html = (
        '<section class="operator-session" '
        'aria-label="Current operator session">'
        '<strong>Operator session</strong>'

        '<div class="operator-row cycle-row">'
        '<span class="operator-label">Session cycle</span>'
        f'<b class="operator-value">{_esc(session_cycle if session_cycle is not None else "N/A")}</b>'
        '</div>'

        '<div class="operator-time-row">'
        '<span class="operator-label">Current log on</span>'
        f'<b class="operator-time">{_esc(current_log_on)}</b>'
        '</div>'

        '<div class="operator-time-row">'
        '<span class="operator-label">Last log on</span>'
        f'<b class="operator-time">{_esc(last_log_on)}</b>'
        '</div>'

        '</section>'
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{_esc(title)}</title>
  <link rel="manifest" href="{_esc(manifest_href)}">
  {pwa_head}
  <style>
    :root {{ color-scheme:dark; --bg:{brand.palette.background}; --panel:{brand.palette.surface}; --panel-2:#182720; --line:#314039; --text:#edf4ef; --muted:#9baba1; --focus:{brand.palette.gold}; }}
    [data-theme="dark"] {{ color-scheme:dark; }}
    [data-theme="light"] {{ color-scheme:light; --bg:#f5f7f9; --panel:#ffffff; --panel-2:#eef2f5; --line:#d3dce2; --text:#13202a; --muted:#63717d; --focus:#8a6a18; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.45 system-ui,sans-serif; }}
    main {{ width:min(720px,100%); margin:auto; padding:calc(18px + env(safe-area-inset-top)) 16px calc(28px + env(safe-area-inset-bottom)); }}
    .brand {{ display:inline-flex; min-height:44px; align-items:center; gap:10px; color:var(--text); text-decoration:none; font-weight:800; font-size:1.25rem; }}
    .brand img {{ width:36px; height:36px; border-radius:8px; }}
    h1 {{ margin:18px 0 4px; font-size:1.6rem; }}
    p {{ color:var(--muted); margin:0 0 18px; }}
    nav {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }}
    .landing-link {{ min-height:52px; display:flex; align-items:center; padding:12px 14px; border:1px solid var(--line); border-radius:8px; background:var(--panel); color:var(--text); text-decoration:none; }}
    .landing-link:hover {{ border-color:var(--focus); }}
    .balance {{ margin:0 0 12px; padding:12px 14px; border:1px solid var(--line); border-radius:8px; display:grid; gap:3px; }}
    .balance span {{ font-size:1.15rem; }} .balance small {{ color:var(--muted); }}
    .operator-session {{ margin:0 0 18px; padding:14px; border:1px solid var(--line); border-radius:8px; }}
    .operator-row {{ margin-top:12px; display:flex; align-items:center; justify-content:space-between; gap:16px; }}
    .operator-time-row {{ margin-top:14px; display:grid; gap:4px; }}
    .operator-label {{ color:var(--muted); }}
    .operator-value {{ font-weight:700; text-align:right; }}
    .operator-time {{ font-weight:650; line-height:1.35; overflow-wrap:normal; word-break:normal; }}
    .theme-control {{ margin:0 0 18px; padding:10px 12px; border:1px solid var(--line); border-radius:8px; background:var(--panel); display:flex; align-items:center; justify-content:space-between; gap:12px; }}
    .theme-control label {{ color:var(--muted); font-weight:650; }}
    .theme-select {{ min-height:40px; padding:6px 10px; border:1px solid var(--line); border-radius:7px; background:var(--panel-2); color:var(--text); font:inherit; font-weight:650; }}
    .theme-select:focus-visible {{ outline:3px solid var(--focus); outline-offset:2px; }}
    a:focus-visible {{ outline:3px solid var(--focus); outline-offset:2px; }}
    footer {{ margin-top:20px; color:var(--muted); font-size:.85rem; }}
    @media(max-width:520px) {{ nav {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main>
    <a class="brand" href="{_esc(navigation.get('canonical_home') or '/mobile-launcher')}" aria-label="CSS Home"><img src="{_esc(brand.asset_url('logo'))}" alt="" aria-hidden="true"><span>CSS</span></a>
    <h1>{_esc(title)}</h1>
    <p>Choose a read-only CSS destination. Mission Control is available but is not the default landing surface.</p>
    {balance_html}
    {operator_html}
    <section class="theme-control" aria-label="Appearance">
      <label for="css-theme-select">Appearance</label>
      <select id="css-theme-select" class="theme-select" aria-label="Appearance">
        <option value="system">System</option>
        <option value="dark">Dark</option>
        <option value="light">Light</option>
      </select>
    </section>
    <nav aria-label="CSS mobile destinations">{links}</nav>
    <footer>Execution remains DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY.</footer>
  </main>
  {service_worker_script}
  <script>
  (function () {{
      const STORAGE_KEY = "css-mobile-theme";
      const root = document.documentElement;
      const selector = document.getElementById("css-theme-select");
      const media = window.matchMedia
          ? window.matchMedia("(prefers-color-scheme: light)")
          : null;

      function systemTheme() {{
          return media && media.matches ? "light" : "dark";
      }}

      function validPreference(value) {{
          return value === "light" ||
                 value === "dark" ||
                 value === "system";
      }}

      function applyTheme(preference) {{
          const pref = validPreference(preference)
              ? preference
              : "system";

          const resolved =
              pref === "system" ? systemTheme() : pref;

          root.setAttribute("data-theme", resolved);

          if (selector) {{
              selector.value = pref;
          }}
      }}

      function loadPreference() {{
          try {{
              const saved = localStorage.getItem(STORAGE_KEY);
              return validPreference(saved) ? saved : "system";
          }} catch (_) {{
              return "system";
          }}
      }}

      let preference = loadPreference();
      applyTheme(preference);

      if (selector) {{
          selector.addEventListener("change", function () {{
              preference = validPreference(selector.value)
                  ? selector.value
                  : "system";

              try {{
                  localStorage.setItem(STORAGE_KEY, preference);
              }} catch (_) {{}}

              applyTheme(preference);
          }});
      }}

      if (media) {{
          const onSystemThemeChange = function () {{
              if (preference === "system") {{
                  applyTheme("system");
              }}
          }};

          if (typeof media.addEventListener === "function") {{
              media.addEventListener("change", onSystemThemeChange);
          }} else if (typeof media.addListener === "function") {{
              media.addListener(onSystemThemeChange);
          }}
      }}
  }})();
  </script>
</body>
</html>"""


def _format_operator_time(value: Any) -> str:
    """Format canonical ISO authentication time for operator display.

    Canonical timestamps remain unchanged internally. Presentation is converted
    to the host's local timezone and rendered compactly for mobile use.
    """
    from datetime import datetime

    raw = str(value or "").strip()
    if not raw:
        return "NOT PREVIOUSLY RECORDED"

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)

        local = parsed.astimezone()

        timezone_label = local.tzname() or local.strftime("%z")

        return (
            f"{local.strftime('%d %b %Y, %I:%M:%S %p')} "
            f"{timezone_label}"
        )
    except (TypeError, ValueError):
        # Never break the mobile landing page because an older artifact uses
        # an unexpected timestamp format.
        return raw


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


__all__ = ["render_mobile_landing"]
