"""
Capital Strata Systems
System Metadata Store — persistent governance metadata

Purpose
- Persist system-level metadata across restarts (e.g., system inception timestamp)
- Provide a single source of truth for time-maturing controls (e.g., 30-day ramp)

Design
- JSON file stored alongside backend/app modules
- Atomic write (write temp → replace)
- Fail-safe: if metadata missing/corrupt, we re-create a minimal file
  (this is acceptable because only deletion/manual wipe should reset inception)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_METADATA_FILENAME = "system_metadata.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, _METADATA_FILENAME)


def load_metadata() -> Dict[str, Any]:
    path = _store_path()
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        # Corrupt/unreadable metadata should not crash the system.
        # Treat as missing; caller may re-create.
        return {}


def save_metadata(meta: Dict[str, Any]) -> None:
    path = _store_path()
    tmp_path = path + ".tmp"

    # Ensure directory exists (should, but safe)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    payload = meta if isinstance(meta, dict) else {}

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)

    # Atomic replace on Windows
    os.replace(tmp_path, path)


def get_system_inception_utc(meta: Optional[Dict[str, Any]] = None) -> str:
    """
    Return the persisted system inception timestamp.
    If missing, create it once and persist it.

    IMPORTANT:
    - This value should only reset if the metadata file is manually deleted/wiped.
    """
    m = meta if isinstance(meta, dict) else load_metadata()

    inception = (m.get("system_inception_utc") or "").strip()
    if inception:
        return inception

    inception = _utc_now_iso()
    m["system_inception_utc"] = inception
    save_metadata(m)
    return inception


def set_system_inception_utc(value_iso: str) -> str:
    """
    Explicitly set inception timestamp (rare; governance action).
    Caller must pass a valid ISO string.
    """
    meta = load_metadata()
    meta["system_inception_utc"] = (value_iso or "").strip()
    save_metadata(meta)
    return meta["system_inception_utc"]


def reset_metadata() -> None:
    """
    Governance-only: delete the metadata file.
    Use this ONLY if you intentionally want to reset the 30-day ramp clock.
    """
    path = _store_path()
    if os.path.exists(path):
        os.remove(path)
