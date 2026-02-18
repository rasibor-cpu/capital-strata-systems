from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict


ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "tracker.csv"
OUT_HTML = ROOT / "dashboard.html"


@dataclass
class Row:
    date: str
    week: int
    category: str
    task_id: str
    priority: str
    status: str
    owner: str
    artifact_or_file: str
    metric_target: str
    metric_actual: str
    notes: str


def load_rows() -> List[Row]:
    rows: List[Row] = []
    with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                Row(
                    date=(r.get("date") or "").strip(),
                    week=int((r.get("week") or "0").strip() or 0),
                    category=(r.get("category") or "").strip(),
                    task_id=(r.get("task_id") or "").strip(),
                    priority=(r.get("priority") or "").strip(),
                    status=(r.get("status") or "").strip().upper(),
                    owner=(r.get("owner") or "").strip(),
                    artifact_or_file=(r.get("artifact_or_file") or "").strip(),
                    metric_target=(r.get("metric_target") or "").strip(),
                    metric_actual=(r.get("metric_actual") or "").strip(),
                    notes=(r.get("notes") or "").strip(),
                )
            )
    return rows


def kpis(rows: List[Row]) -> Dict[str, int]:
    current_week = max((r.week for r in rows), default=1)
    done = sum(1 for r in rows if r.status == "DONE")
    blocked = sum(1 for r in rows if r.status == "BLOCKED")
    open_count = sum(1 for r in rows if r.status in ("TODO", "DOING"))
    total = max(len(rows), 1)
    pct_done = int(round((done / total) * 100))
    return {
        "current_week": current_week,
        "done": done,
        "blocked": blocked,
        "open": open_count,
        "total": len(rows),
        "pct_done": pct_done,
    }


def week_summary(rows: List[Row], week: int) -> str:
    wk = [r for r in rows if r.week == week]
    if not wk:
        return f"No tasks logged for week {week} yet."

    by_status: Dict[str, List[Row]] = {}
    for r in wk:
        by_status.setdefault(r.status, []).append(r)

    lines = []
    for status in ("BLOCKED", "DOING", "TODO", "DONE"):
        items = by_status.get(status, [])
        if not items:
            continue
        lines.append(f"{status} ({len(items)}):")
        for it in items[:20]:
            lines.append(f"  - {it.task_id} [{it.priority}] {it.category}: {it.notes or it.artifact_or_file}")
        if len(items) > 20:
            lines.append(f"  ... +{len(items) - 20} more")
        lines.append("")
    return "\n".join(lines).rstrip()


def html_rows(rows: List[Row]) -> str:
    def esc(x: str) -> str:
        return (
            x.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
        )

    out = []
    for r in rows:
        out.append(
            "<tr>"
            f"<td>{esc(r.date)}</td>"
            f"<td>{r.week}</td>"
            f"<td>{esc(r.category)}</td>"
            f"<td>{esc(r.task_id)}</td>"
            f"<td>{esc(r.priority)}</td>"
            f"<td class='{esc(r.status)}'>{esc(r.status)}</td>"
            f"<td>{esc(r.artifact_or_file)}</td>"
            f"<td>{esc(r.metric_target)}</td>"
            f"<td>{esc(r.metric_actual)}</td>"
            f"<td>{esc(r.notes)}</td>"
            "</tr>"
        )
    return "\n".join(out)


def main() -> int:
    if not CSV_PATH.exists():
        print(f"[ops] Missing: {CSV_PATH}")
        return 2

    rows = load_rows()
    k = kpis(rows)
    summary = week_summary(rows, k["current_week"])

    template_path = ROOT / "dashboard_template.html"
    if not template_path.exists():
        print(f"[ops] Missing: {template_path}")
        return 3

    html = template_path.read_text(encoding="utf-8")
    html = html.replace("{{generated_at}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    html = html.replace("{{current_week}}", str(k["current_week"]))
    html = html.replace("{{pct_done}}", str(k["pct_done"]))
    html = html.replace("{{open_count}}", str(k["open"]))
    html = html.replace("{{blocked_count}}", str(k["blocked"]))
    html = html.replace("{{week_summary}}", summary)
    html = html.replace("{{rows}}", html_rows(rows))

    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"[ops] Wrote: {OUT_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
