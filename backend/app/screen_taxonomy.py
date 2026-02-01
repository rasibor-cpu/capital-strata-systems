"""
REA Capital Trading Engine
Screen Taxonomy & Deterministic Screen IDs

Purpose
- Single source of truth for screen identifiers.
- Enforce deterministic naming across UI surfaces (web/admin/ops/mobile/cli).
- Prevent "stringly-typed" screen routing chaos.

ID RULES (LOCKED)
- screen_id is lowercase snake_case
- screen_id must be stable and descriptive (no version suffixes)
- screen_id must not encode UI technology (no "react_", "android_", etc.)
- screen_id must map to exactly one handler in ScreenRegistry
"""

from dataclasses import dataclass
from typing import Dict, List


# ---------------------------------------------------------------------
# Taxonomy dimensions
# ---------------------------------------------------------------------

DOMAIN = {
    "core": "core platform screens",
    "auth": "user access and security",
    "ops": "operations and monitoring",
    "engine": "prompt-only engine diagnostics and replay",
    "risk": "risk controls and governance",
    "reporting": "reports and exports",
    "admin": "system administration",
    "posting": "maker-checker posting, approvals, tickets, ledger posting",
}

CATEGORY = {
    "dashboard": "overview / summary",
    "form": "data entry or configuration",
    "viewer": "read-only detail display",
    "wizard": "multi-step flow",
    "report": "report generation / export",
    "console": "diagnostics / logs / tools",
}


# ---------------------------------------------------------------------
# Canonical screen definitions
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class ScreenDef:
    screen_id: str
    domain: str
    category: str
    title: str
    description: str


SCREENS: List[ScreenDef] = [
    # -------------------------
    # Core / Ops
    # -------------------------
    ScreenDef(
        screen_id="health_check",
        domain="core",
        category="console",
        title="Health Check",
        description="Sanity check that orchestration is online (prompt-only).",
    ),
    ScreenDef(
        screen_id="diagnostics",
        domain="ops",
        category="console",
        title="Diagnostics Console",
        description="Basic diagnostics and request echo for troubleshooting.",
    ),
    ScreenDef(
        screen_id="screen_index",
        domain="core",
        category="dashboard",
        title="Screen Index",
        description="List and search all registered screens (admin/dev use).",
    ),

    # -------------------------
    # Engine / Risk / Reporting
    # -------------------------
    ScreenDef(
        screen_id="engine_replay_runner",
        domain="engine",
        category="wizard",
        title="Replay Runner",
        description="Run CSV replay (prompt-only) and view summary results.",
    ),
    ScreenDef(
        screen_id="risk_override_review",
        domain="risk",
        category="viewer",
        title="Risk Override Review",
        description="Review override requests, decisions, and audit trail.",
    ),
    ScreenDef(
        screen_id="reports_center",
        domain="reporting",
        category="report",
        title="Reports Center",
        description="Generate and export system reports (EOD/monthly/year-end).",
    ),

    # -------------------------
    # Posting (Maker-Checker)
    # -------------------------
    ScreenDef(
        screen_id="posting_entry",
        domain="posting",
        category="form",
        title="Posting Entry",
        description="Maker creates a posting ticket (draft; validation + store).",
    ),
    ScreenDef(
        screen_id="posting_submit",
        domain="posting",
        category="wizard",
        title="Posting Submit",
        description="Maker submits DRAFT ticket for checker review (DRAFT -> SUBMITTED).",
    ),
    ScreenDef(
        screen_id="posting_review",
        domain="posting",
        category="viewer",
        title="Posting Review",
        description="Read-only review of a posting ticket prior to approval.",
    ),
    ScreenDef(
        screen_id="posting_approval",
        domain="posting",
        category="wizard",
        title="Posting Approval",
        description="Checker approves/rejects/returns posting ticket (no ledger write yet).",
    ),
    ScreenDef(
        screen_id="posting_result",
        domain="posting",
        category="viewer",
        title="Posting Result",
        description="Shows outcome, approvals, and audit trail for a ticket.",
    ),
]


# ---------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------

def build_screen_index() -> Dict[str, ScreenDef]:
    index: Dict[str, ScreenDef] = {}
    for s in SCREENS:
        if s.screen_id in index:
            raise ValueError(f"Duplicate screen_id in taxonomy: {s.screen_id}")
        if s.domain not in DOMAIN:
            raise ValueError(f"Invalid domain in taxonomy: {s.domain} (screen_id={s.screen_id})")
        if s.category not in CATEGORY:
            raise ValueError(f"Invalid category in taxonomy: {s.category} (screen_id={s.screen_id})")
        index[s.screen_id] = s
    return index


SCREEN_INDEX = build_screen_index()


def list_screen_ids() -> List[str]:
    return sorted(SCREEN_INDEX.keys())
