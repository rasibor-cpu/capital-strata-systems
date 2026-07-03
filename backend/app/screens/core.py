"""
Core and Ops screen handlers (Phase 12.3)

Handlers remain:
- prompt-only
- routing/diagnostics only
- no execution, no risk escalation
"""

import datetime
from typing import Dict, Any

from ..screen_taxonomy import SCREEN_INDEX, list_screen_ids


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None).isoformat()


def health_check_handler(registry_keys: Dict[str, bool]) -> Dict[str, Any]:
    """
    Returns a dict payload for health-check response.
    registry_keys: mapping of screen_id -> registered True/False (computed by main)
    """
    return {
        "server_time": _now_iso(),
        "engine_mode": "prompt-only",
        "execution_enabled": False,
        "registered_screens": sorted([k for k, v in registry_keys.items() if v]),
        "known_screens": list_screen_ids(),
    }


def diagnostics_handler(action: str, payload: Dict[str, Any], screen_id: str) -> Dict[str, Any]:
    return {
        "requested_action": action,
        "payload_keys": list(payload.keys()),
        "screen_def": SCREEN_INDEX[screen_id].__dict__,
    }


def screen_index_handler(registry_keys: Dict[str, bool]) -> Dict[str, Any]:
    items = [
        {
            "screen_id": sid,
            "domain": SCREEN_INDEX[sid].domain,
            "category": SCREEN_INDEX[sid].category,
            "title": SCREEN_INDEX[sid].title,
            "description": SCREEN_INDEX[sid].description,
            "registered": bool(registry_keys.get(sid, False)),
        }
        for sid in list_screen_ids()
    ]
    return {"screens": items}
