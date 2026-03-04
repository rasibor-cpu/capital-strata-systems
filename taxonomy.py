"""
taxonomy.py (repo root)
Capital Strata Systems (CSS)

Purpose (bootstrap):
- Provide SCREEN_TAXONOMY so main.py can import cleanly.
- Keep this minimal for live-protocol activation.
- We will harden/expand taxonomy later (post Phase-1 stabilization).
"""

from __future__ import annotations

# Minimal screen taxonomy map.
# Expand later with your actual UI/reporting routing taxonomy.
SCREEN_TAXONOMY = {
    "version": "0.0.1-bootstrap",
    "screens": {},
}