from __future__ import annotations

import csv
import html
import io
import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    media_type: str
    content: str
    filename: str


def _flatten(
    value: Any,
    *,
    prefix: str = "",
) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten(value[key], prefix=child))
        return rows
    if isinstance(value, list):
        for index, item in enumerate(value):
            child = f"{prefix}[{index}]"
            rows.extend(_flatten(item, prefix=child))
        if not value:
            rows.append((prefix, []))
        return rows
    rows.append((prefix, value))
    return rows


def export_payload(
    *,
    title: str,
    payload: Any,
    format_name: str,
    filename_stem: str,
) -> ExportArtifact:
    fmt = (format_name or "").strip().lower()
    if fmt == "json":
        return ExportArtifact(
            media_type="application/json",
            content=json.dumps(
                payload,
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n",
            filename=f"{filename_stem}.json",
        )

    rows = _flatten(payload)

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["field", "value"])
        for field, value in rows:
            writer.writerow(
                [
                    field,
                    json.dumps(value, default=str)
                    if isinstance(value, (dict, list))
                    else value,
                ]
            )
        return ExportArtifact(
            media_type="text/csv",
            content=output.getvalue(),
            filename=f"{filename_stem}.csv",
        )

    if fmt == "text":
        lines = [title, "=" * len(title)]
        for field, value in rows:
            lines.append(f"{field}: {value}")
        return ExportArtifact(
            media_type="text/plain",
            content="\n".join(lines) + "\n",
            filename=f"{filename_stem}.txt",
        )

    if fmt == "html":
        body_rows = "".join(
            "<tr><th>"
            + html.escape(field)
            + "</th><td>"
            + html.escape(str(value))
            + "</td></tr>"
            for field, value in rows
        )
        document = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{html.escape(title)}</title>"
            "<style>body{font-family:system-ui,sans-serif;margin:24px}"
            "table{border-collapse:collapse;width:100%}"
            "th,td{border:1px solid #ccc;padding:8px;text-align:left}"
            "th{width:35%}</style></head><body>"
            f"<h1>{html.escape(title)}</h1><table>{body_rows}</table>"
            "</body></html>"
        )
        return ExportArtifact(
            media_type="text/html",
            content=document,
            filename=f"{filename_stem}.html",
        )

    raise ValueError("format must be one of: json, csv, html, text")
