from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from typing import Any


def page_header(title: str, description: str) -> str:
    return (
        '<header class="mc-page-header">'
        f"<div><p class=\"mc-eyebrow\">CSS Mission Control</p><h1>{escape(title)}</h1>"
        f"<p>{escape(description)}</p></div>"
        '<span class="mc-badge neutral">READ ONLY</span>'
        "</header>"
    )


def metric_grid(items: Sequence[tuple[str, Any, str]]) -> str:
    cards = []
    for label, value, status in items:
        cards.append(
            '<article class="mc-metric-card">'
            f"<span>{escape(label)}</span>"
            f"<strong>{escape(value)}</strong>"
            f'<em class="mc-status {status_class(status)}">{escape(status)}</em>'
            "</article>"
        )
    return f'<section class="mc-metric-grid">{"".join(cards)}</section>'


def detail_table(title: str, rows: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> str:
    if isinstance(rows, Mapping):
        body = "".join(f"<tr><th>{escape(key)}</th><td>{escape(value)}</td></tr>" for key, value in rows.items())
        if not body:
            body = '<tr><td colspan="2">No evidence available.</td></tr>'
    else:
        normalized = [row for row in rows if isinstance(row, Mapping)]
        headers = list(normalized[0].keys()) if normalized else []
        header = (
            "<thead><tr>"
            + "".join(f"<th>{escape(key)}</th>" for key in headers)
            + "</tr></thead>"
            if headers
            else ""
        )
        body_rows = "".join(
            "<tr>"
            + "".join(f"<td>{escape(row.get(key))}</td>" for key in headers)
            + "</tr>"
            for row in normalized
        )
        body = header + f"<tbody>{body_rows}</tbody>" if body_rows else '<tbody><tr><td>No evidence available.</td></tr></tbody>'
    return f'<section class="mc-panel"><h2>{escape(title)}</h2><table>{body}</table></section>'


def split_panels(*panels: str) -> str:
    return f'<div class="mc-panel-grid">{"".join(panels)}</div>'


def warning_banner(message: str, *, status: str = "blocked") -> str:
    return f'<div class="mc-warning {status_class(status)}">{escape(message)}</div>'


def escape(value: Any) -> str:
    if value is None:
        return "UNAVAILABLE"
    if isinstance(value, (dict, list, tuple)):
        return html.escape(str(value), quote=True)
    return html.escape(str(value), quote=True)


def status_class(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "-")
    if any(token in text for token in ("green", "pass", "ready", "normal", "available", "ok")):
        return "good"
    if any(token in text for token in ("amber", "warning", "monitor")):
        return "warn"
    if any(token in text for token in ("red", "fail", "blocked", "unavailable", "disabled")):
        return "bad"
    return "neutral"


def section(state: Mapping[str, Any], name: str) -> dict[str, Any]:
    value = state.get(name)
    return dict(value) if isinstance(value, Mapping) else {}
