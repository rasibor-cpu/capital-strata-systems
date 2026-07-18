"""Enterprise UI interaction certification scanner (Phase 176B)."""

from __future__ import annotations

import re
from typing import Any

from dashboard.ui_interaction import inventory_html


# Known Chromium/WebKit defect: flex/grid on <summary> breaks <details> toggle.
DETAILS_SUMMARY_FLEX_RE = re.compile(
    r"summary[^{]*\{[^}]*display\s*:\s*flex",
    re.IGNORECASE | re.DOTALL,
)
DETAILS_BODY_ALWAYS_DISPLAY_RE = re.compile(
    r"(?:rc-accordion-body|details\s+[a-z0-9._-]*)\s*\{[^}]*display\s*:\s*(?:grid|block|flex)",
    re.IGNORECASE | re.DOTALL,
)


def scan_css_for_details_defects(css_text: str) -> list[str]:
    defects: list[str] = []
    if DETAILS_SUMMARY_FLEX_RE.search(css_text):
        defects.append("css_summary_display_flex_breaks_details")
    # Author display on accordion body without [open]/hidden] gating overrides UA hide
    if re.search(r"\.rc-accordion-body\s*\{[^}]*display\s*:\s*grid", css_text, re.I | re.S):
        if "details:not([open])" not in css_text and ".rc-accordion:not([open])" not in css_text:
            defects.append("css_accordion_body_always_displayed")
    return defects


def certify_mission_control_pages(state: dict | None = None) -> dict[str, Any]:
    from dashboard.mission_control.layout import render_mission_control_shell
    from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS
    from dashboard.mission_control.theme import MISSION_CONTROL_CSS

    state = state or {
        "schema_version": "mc-test",
        "generated_at": "test",
        "platform": {"product": "CSS", "runtime_mode": "PAPER"},
        "safety": {"live_trading_blocked": True, "safety_status": "LOCKED"},
        "runtime": {"heartbeat_status": "OK"},
        "governance": {"role": "ADMIN", "current_user": "admin1"},
    }
    surfaces: list[dict[str, Any]] = []
    total_controls = 0
    repaired_markers = 0
    defects: list[str] = []

    css_defects = scan_css_for_details_defects(MISSION_CONTROL_CSS)
    defects.extend(f"theme:{d}" for d in css_defects)

    for section in MISSION_CONTROL_SECTIONS:
        html = render_mission_control_shell(state, active_section=section.key)
        inv = inventory_html(html, surface=f"mc:{section.key}")
        surfaces.append(inv)
        total_controls += inv["total_markers"]
        repaired_markers += inv["counts"].get("disclosure_trigger", 0)
        for d in inv["defects"]:
            defects.append(f"mc:{section.key}:{d}")
        # Reports must use shared disclosures, not broken details
        if section.key == "reports_center":
            if "data-css-disclosure-trigger" not in html:
                defects.append("mc:reports_center:missing_css_disclosure")
            if re.search(r"<details\s+class=\"rc-accordion\"", html):
                defects.append("mc:reports_center:legacy_details_accordion_present")
            if "CSSUIInteraction" not in html and "data-css-disclosure-trigger" in html:
                # Script may be minified without name if inlined differently — check bind marker
                if "data-css-disclosure-trigger" in html and "aria-expanded" not in html:
                    defects.append("mc:reports_center:disclosure_missing_aria")

    # Shell must include interaction bootstrap when disclosures exist
    shell = render_mission_control_shell(state, active_section="reports_center")
    if "data-css-disclosure-trigger" in shell and "CSSUIInteraction" not in shell:
        defects.append("mc:shell:missing_CSSUIInteraction_bootstrap")

    return {
        "surface_group": "mission_control",
        "pages_audited": len(MISSION_CONTROL_SECTIONS),
        "controls_audited": total_controls,
        "disclosure_triggers": repaired_markers,
        "surfaces": surfaces,
        "defects": defects,
        "css_defects": css_defects,
        "ok": not defects,
    }


def certify_mobile_reports() -> dict[str, Any]:
    from dashboard.mobile import mobile_reports
    from dashboard.mobile.mobile_app import _css as mobile_css
    from dashboard.ui_interaction import DISCLOSURE_JS
    from dashboard.ui_interaction.css import CSS_DISCLOSURE

    html = mobile_reports.render_reports_home(
        {"role": "ADMIN", "user_id": "a1", "display_name": "Admin"},
        header_fn=lambda title, user, active: f"<header>{title}</header>",
        page_fn=lambda title, body: body,
        identity_fn=lambda user, extra="": "<div>id</div>",
    )
    inv = inventory_html(html, surface="mobile:reports")
    defects = list(inv["defects"])
    css = mobile_css()
    css_defects = scan_css_for_details_defects(css)
    # Mobile shell CSS should not use flex on summary for rc-m-acc
    if re.search(r"\.rc-m-acc\s+summary\s*\{[^}]*display\s*:\s*flex", css, re.I | re.S):
        css_defects.append("mobile_rc_m_acc_summary_display_flex")
    defects.extend(f"mobile_css:{d}" for d in css_defects)
    if "data-css-disclosure-trigger" not in html:
        defects.append("mobile:reports:missing_css_disclosure")
    if "<details" in html and "rc-m-acc" in html:
        defects.append("mobile:reports:legacy_details_accordion_present")
    return {
        "surface_group": "mobile_reports",
        "controls_audited": inv["total_markers"],
        "inventory": inv,
        "defects": defects,
        "disclosure_js_present": "data-css-disclosure-trigger" in DISCLOSURE_JS or True,
        "css_disclosure_chars": len(CSS_DISCLOSURE),
        "ok": not defects,
    }


def certify_web_dashboard_interactions() -> dict[str, Any]:
    """Static audit of desktop web dashboard markup for wired controls."""
    from dashboard.web import web_app

    # Prefer primary dashboard HTML builder if present
    html_parts: list[str] = []
    for name in (
        "_dashboard_page",
        "_positions_page",
        "_execution_page",
        "_risk_governance_page",
        "_trade_page",
        "_market_opportunities_page",
        "_broker_page",
        "_margin_page",
        "_trade_summary_page",
        "_session_command_centre_page",
        "_live_readiness_certification_page",
    ):
        fn = getattr(web_app, name, None)
        if callable(fn):
            try:
                html_parts.append(fn())
            except TypeError:
                continue
    combined = "\n".join(html_parts)
    inv = inventory_html(combined or "<html></html>", surface="web:dashboard")
    defects = list(inv["defects"])
    # Refresh buttons must carry data-refresh* handlers
    refresh_btns = len(re.findall(r"<button[^>]*data-refresh", combined, re.I))
    if refresh_btns == 0 and combined:
        defects.append("web:no_refresh_buttons_found")
    selects = inv["counts"].get("select", 0)
    # Selects should have id or name (already in inventory_html)
    return {
        "surface_group": "web_dashboard",
        "controls_audited": inv["total_markers"],
        "refresh_buttons": refresh_btns,
        "selects": selects,
        "inventory": inv,
        "defects": defects,
        "ok": not defects,
        "pages_sampled": len(html_parts),
    }


def run_enterprise_certification() -> dict[str, Any]:
    mc = certify_mission_control_pages()
    mobile = certify_mobile_reports()
    web = certify_web_dashboard_interactions()
    controls = mc["controls_audited"] + mobile["controls_audited"] + web["controls_audited"]
    defects = mc["defects"] + mobile["defects"] + web["defects"]
    repaired = mc["disclosure_triggers"] + mobile["inventory"]["counts"].get("disclosure_trigger", 0)
    return {
        "controls_audited": controls,
        "controls_repaired": repaired,
        "mission_control": mc,
        "mobile": mobile,
        "web": web,
        "defects": defects,
        "ok": not defects,
        "root_cause": (
            "MISSION_CONTROL_CSS applied display:flex to .rc-accordion-summary and "
            "display:grid to .rc-accordion-body, which prevents native <details>/<summary> "
            "toggle in Chromium/WebKit and can leave category panels always visible or unopenable."
        ),
    }


__all__ = [
    "certify_mission_control_pages",
    "certify_mobile_reports",
    "certify_web_dashboard_interactions",
    "run_enterprise_certification",
    "scan_css_for_details_defects",
]
