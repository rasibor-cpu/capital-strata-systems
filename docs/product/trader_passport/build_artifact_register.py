"""PAPS-001 artifact register for the Trader Passport work (Issue #102).

    python3 docs/product/trader_passport/build_artifact_register.py
Lists every file this branch adds or changes relative to the START commit, with sha256, size, category, provenance
and PAPS status. Run last, after all other files are final.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
START_SHA = "df566eee3fa2aeee65925ebc26ac193c2221d27e"
OUT = Path(__file__).resolve().parent / "ARTIFACT_REGISTER.json"


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, check=True).stdout


changed = set(git("diff", "--name-only", START_SHA).split()) | set(git("ls-files", "--others", "--exclude-standard").split())
changed.discard(str(OUT.relative_to(ROOT)))


def category(p: str) -> tuple[str, str]:
    if p.endswith(".svg"):
        return "graphic", "Original hand-authored SVG, created 2026-10-05 for Issue #102; no external source, no third-party artwork"
    if "/screenshots/" in p:
        return "screenshot evidence", "Playwright/Chromium capture of the local standalone app, S24 emulation unless named otherwise; synthetic data"
    if p.startswith("tests/"):
        return "test", "Written for Issue #102"
    if p.startswith("docs/"):
        return "documentation / evidence", "Written or generated for Issue #102"
    if p.startswith("frontend/"):
        return "ui source", "Original CSS UI code for Issue #102"
    return "source", "Written for Issue #102"


rows = []
for p in sorted(changed):
    f = ROOT / p
    if not f.exists():
        continue
    cat, prov = category(p)
    rows.append({"path": p, "bytes": f.stat().st_size, "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                 "category": cat, "provenance": prov,
                 "status": "COMPLETED — PRESERVED once this commit is pushed to claude/css-trader-passport-102"})
register = {
    "standard": "PAPS-001", "work_item": "rasibor-cpu/capital-strata-systems#102",
    "branch": "claude/css-trader-passport-102", "start_sha": START_SHA, "created_on": "2026-10-05",
    "questionnaire_version": "TP-Q-1.0.0", "rules_version": "TP-R-1.0.0", "origin_policy_version": "TO-1.0.0",
    "search_before_create": [
        "No existing onboarding, questionnaire or trader-profile code found (grep across repo, excluding archives)",
        "Existing trade attribution (scripts/css_trade_attribution.py) is P&L by asset class only, no origin: extended by a new module, not replaced",
        "Existing legal acceptance (backend/app/compliance/legal_acceptance*) reused as the authority; onboarding acknowledgements explicitly are not legal acceptance",
        "Existing auth (backend/app/auth token_store) reused for sessions",
        "No existing CSS illustration set found for onboarding; 8 new SVGs created",
    ],
    "not_preserved_in_git": [
        {"item": "full-resolution PNG screenshots (21 MB)", "reason": "size; preserved as full-resolution WebP (quality 80) in evidence/screenshots"},
        {"item": "test virtualenv, Playwright browser, axe-core 4.14.0 package", "reason": "third-party tooling, reinstallable; versions recorded in evidence"},
    ],
    "generated_not_preserved": [],
    "files": rows,
}
OUT.write_text(json.dumps(register, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(len(rows), "files registered")
