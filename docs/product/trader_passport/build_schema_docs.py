"""Export the Trader Passport questionnaire to versioned JSON + readable Markdown (PAPS-001 record).

    python3 docs/product/trader_passport/build_schema_docs.py
Source of truth stays backend/app/onboarding/schema.py; these files are derived and must be regenerated after edits.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from backend.app.onboarding.schema import QUESTIONNAIRE_VERSION, STAGES  # noqa: E402

OUT = Path(__file__).resolve().parent
(OUT / f"QUESTION_SCHEMA_{QUESTIONNAIRE_VERSION}.json").write_text(
    json.dumps({"version": QUESTIONNAIRE_VERSION, "stages": STAGES}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

lines = [f"# CSS Trader Passport question schema ({QUESTIONNAIRE_VERSION})", "",
         "Generated from `backend/app/onboarding/schema.py` by `build_schema_docs.py`. Do not edit by hand.", "",
         "| # | Stage | Kind | Shown when | Questions |", "|---|---|---|---|---|"]
for i, s in enumerate(STAGES, 1):
    cond = json.dumps(s["show_if"]) if s.get("show_if") else "always"
    qs = "<br>".join(f"`{q['id']}` ({q['type']}{', required' if q.get('required') else ''}{', sensitive' if q.get('sensitive') else ''}): {q['prompt']}"
                     for q in s.get("questions", [])) or "—"
    lines.append(f"| {i} | `{s['id']}` — {s['title']} | {s['kind']} | {cond.replace('|', '/')} | {qs.replace('|', '/')} |")
lines += ["", "## Options", ""]
for s in STAGES:
    for q in s.get("questions", []):
        if q.get("options"):
            opts = "; ".join(f"`{o['value']}` {o['label']}" for o in q["options"])
            extra = f" — correct: `{q['correct']}`" if "correct" in q else ""
            lines.append(f"- `{q['id']}`: {opts}{extra}")
        if q.get("rows"):
            lines.append(f"  - rows: {', '.join(r['label'] for r in q['rows'])}")
(OUT / "QUESTION_SCHEMA.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("exported", QUESTIONNAIRE_VERSION, len(STAGES), "stages")
