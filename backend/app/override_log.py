"""
override_log.py
---------------
Immutable Override Log (Append-only, Hash-Chained)

Purpose:
- Provide regulator/auditor-grade evidence of overrides.
- Ensure overrides are traceable, tamper-evident, and reasoned.
- Fail-closed philosophy: if we cannot log an override, the action must be blocked.

File:
- audit_logs/overrides.jsonl  (repo-root anchored)

Record model (per line):
{
  "ts_utc": "...",
  "event": "OVERRIDE",
  "override_id": "...",
  "actor_user_id": "...",
  "override_type": "...",
  "reason": "...",
  "scope": {...},
  "approval_level": "...",
  "prev_hash": "...",
  "hash": "..."
}
"""

from __future__ import annotations

import json
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _repo_root() -> Path:
    # backend/app/override_log.py -> parents[2] is repo root
    return Path(__file__).resolve().parents[2]


def _log_path() -> Path:
    root = _repo_root()
    out_dir = root / "audit_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "overrides.jsonl"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_json(obj: Dict[str, Any]) -> str:
    # Deterministic serialization for hashing
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_last_hash(path: Path) -> str:
    if not path.exists():
        return "GENESIS"
    try:
        # Read last non-empty line
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return "GENESIS"

            # Scan backwards for newline
            step = 4096
            pos = max(0, size - step)
            while True:
                f.seek(pos)
                chunk = f.read(size - pos)
                lines = chunk.splitlines()
                if len(lines) >= 1:
                    last = lines[-1].decode("utf-8", errors="ignore").strip()
                    if last:
                        rec = json.loads(last)
                        return str(rec.get("hash", "GENESIS"))
                if pos == 0:
                    break
                size = pos
                pos = max(0, pos - step)
    except Exception:
        return "GENESIS"
    return "GENESIS"


def write_override(
    *,
    actor_user_id: str,
    override_type: str,
    reason: str,
    scope: Optional[Dict[str, Any]] = None,
    approval_level: str = "CHECKER",
    override_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Writes a single override record (append-only, hash-chained).

    Returns the full record (including override_id + hashes).

    Raises on any failure (caller should fail-closed).
    """
    actor_user_id = (actor_user_id or "").strip() or "unknown_actor"
    override_type = (override_type or "").strip()
    reason = (reason or "").strip()
    scope = scope or {}

    if not override_type:
        raise ValueError("override_type is required")
    if not reason:
        raise ValueError("reason is required for override logging")

    path = _log_path()
    prev_hash = _read_last_hash(path)

    rec_core: Dict[str, Any] = {
        "ts_utc": _now_utc_iso(),
        "event": "OVERRIDE",
        "override_id": override_id or str(uuid.uuid4()),
        "actor_user_id": actor_user_id,
        "override_type": override_type,
        "reason": reason,
        "scope": scope,
        "approval_level": approval_level,
        "prev_hash": prev_hash,
    }

    rec_hash = _sha256(_canonical_json(rec_core))
    rec = dict(rec_core)
    rec["hash"] = rec_hash

    line = json.dumps(rec, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)

    return rec