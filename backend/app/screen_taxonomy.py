"""
REA Capital Trading Engine
Phase 12.2 — Screen Taxonomy & Deterministic Screen IDs

Purpose
- Provide a single source of truth for screen identifiers.
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

# Domain areas (what business/system area the screen belongs to)
DOMAIN = {
    "core": "core platform screens",
    "auth": "user access and security",
    "ops": "operations and monitoring",
    "engine": "prompt-only engine diagnostics and replay",
    "risk": "risk controls and governance",
    "reporting": "reports and exports",
    "admin": "system administration",
}

# Screen categories (how the screen behaves)
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
    # Core
    ScreenDef(
        screen_id="health_check",
        domain="core",
        category="console",
        title="Health Check",
        description="Sanity check that orchestration is online (prompt-only).",
    ),

    # Ops / Diagnostics
    ScreenDef(
        screen_id="diagnostics",
        domain="ops",
        category="console",
        title="Diagnostics Console",
        description="Basic diagnostics and request echo for troubleshooting.",
    ),

    # Future Phase 12.x (pre-declared to stabilize IDs early)
    ScreenDef(
        screen_id="screen_index",
        domain="core",
        category="dashboard",
        title="Screen Index",
        description="List and search all registered screens (admin/dev use).",
    ),
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
]


# ---------------------------------------------------------------------
# Validation helpers (used in main orchestration)
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
