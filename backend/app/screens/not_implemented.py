"""
Not Implemented screen handler (Phase 12.5)

Used to safely wire taxonomy-defined screens before their full build.
"""

from typing import Dict, Any


def not_implemented_payload(screen_id: str, action: str) -> Dict[str, Any]:
    return {
        "screen_id": screen_id,
        "action": action,
        "status": "not_implemented",
        "message": "Screen is defined in taxonomy but not implemented yet.",
        "next_step": "Implement handler and register it in main.py (Phase 12.x).",
    }
