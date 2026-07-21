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
    account_value_display = (
        f"{account_value.get('value')} {account_value.get('currency')}"
        if account_value.get("availability_state") == "AVAILABLE"
        else "UNAVAILABLE"
    )
    balance_html = (
        '<section class="balance" aria-label="Account balance summary">'
        "<strong>Account value</strong>"
        f"<span>{_esc(account_value_display)}</span>"
        f"<small>{_esc(account_value.get('availability_state') or 'UNAVAILABLE')} · "
        f"{_esc(account_value.get('provenance') or 'UNAVAILABLE')}</small></section>"
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
    :root {{ color-scheme: dark; --bg:{brand.palette.background}; --panel:{brand.palette.surface}; --line:#314039; --text:#edf4ef; --muted:#9baba1; --focus:{brand.palette.gold}; }}
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
    .balance {{ margin:0 0 18px; padding:12px 14px; border:1px solid var(--line); border-radius:8px; display:grid; gap:3px; }}
    .balance span {{ font-size:1.15rem; }} .balance small {{ color:var(--muted); }}
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
    <nav aria-label="CSS mobile destinations">{links}</nav>
    <footer>Execution remains DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY.</footer>
  </main>
  {service_worker_script}
</body>
</html>"""


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


__all__ = ["render_mobile_landing"]
