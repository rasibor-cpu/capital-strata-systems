"""Export the CSS UI function capability matrix markdown."""

from __future__ import annotations

from dashboard.ui_function.registry import all_controls, registry_summary


def render_capability_matrix_markdown() -> str:
    summary = registry_summary()
    lines = [
        "# CSS UI Function Capability Matrix",
        "",
        "Phase 176C machine-readable registry export.",
        "",
        f"- Total controls: **{summary['total_controls']}**",
        f"- Pages audited: **{summary['pages_audited']}**",
        f"- Sub-tabs audited: **{summary['subtabs_audited']}**",
        f"- Status counts: `{summary['by_status']}`",
        "",
        "| control_id | page | label | type | desktop_route | mobile_route | api/service | status | desktop/mobile | limitation | test_id |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in all_controls():
        api = c.expected_api or c.expected_service or "—"
        lim = (c.limitation or "").replace("|", "/")
        lines.append(
            f"| `{c.control_id}` | {c.page_id} | {c.label} | {c.control_type} | "
            f"{c.desktop_route or '—'} | {c.mobile_route or '—'} | {api} | "
            f"**{c.implementation_status}** | {c.desktop_mobile} | {lim or '—'} | `{c.test_id or '—'}` |"
        )
    lines.append("")
    lines.append("## Status legend")
    lines.append("")
    lines.append("- FUNCTIONAL — end-to-end intended workflow verified")
    lines.append("- FUNCTIONAL_WITH_LIMITATIONS — works with documented limits")
    lines.append("- FAIL_CLOSED — intentionally non-writable / denied")
    lines.append("- DISABLED / COMING_SOON — not presented as operational")
    lines.append("- BROKEN — must be zero at phase completion")
    lines.append("- UNVERIFIED — must be zero at phase completion")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_capability_matrix_markdown())
