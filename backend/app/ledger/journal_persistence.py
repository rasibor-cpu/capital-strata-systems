"""
journal_persistence.py
Capital Strata Systems (CSS)

Append-Only Journal Log (Phase 2 – Tamper Evident)
--------------------------------------------------

Now includes:
- SHA256 hash chain
- previous_hash linking
- Deterministic canonical hashing
- Full chain verification
- Fail-closed rebuild support

Design:
hash_n = SHA256(previous_hash + canonical_payload)

If any historical entry changes,
all subsequent hashes break.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple


# ==========================================================
# CONFIG
# ==========================================================

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
DATA_DIR = BASE_DIR / "data"
JOURNAL_FILE = DATA_DIR / "journal.log"

GENESIS_HASH = "0" * 64  # 64-char zero string


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# HASHING
# ==========================================================

def _canonical_json(obj: Dict[str, Any]) -> str:
    """
    Deterministic JSON serialization.
    """
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ==========================================================
# WRITE (Append)
# ==========================================================

def append_payload(payload: Dict[str, Any]) -> None:
    """
    Append payload with hash chain protection.
    """

    _ensure_data_dir()

    previous_hash = GENESIS_HASH

    if JOURNAL_FILE.exists():
        with JOURNAL_FILE.open("rb") as f:
            try:
                f.seek(-2, 2)
                while f.read(1) != b"\n":
                    f.seek(-2, 1)
            except OSError:
                f.seek(0)
            last_line = f.readline().decode().strip()
            if last_line:
                last_obj = json.loads(last_line)
                previous_hash = last_obj.get("hash", GENESIS_HASH)

    canonical = _canonical_json(payload)
    current_hash = _sha256_hex(previous_hash + canonical)

    wrapped = {
        "previous_hash": previous_hash,
        "hash": current_hash,
        "payload": payload,
    }

    line = _canonical_json(wrapped)

    with JOURNAL_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ==========================================================
# READ
# ==========================================================

def load_all_payloads() -> List[Dict[str, Any]]:
    """
    Load and verify entire hash chain.
    Fail-closed if chain breaks.
    """
    if not JOURNAL_FILE.exists():
        return []

    payloads: List[Dict[str, Any]] = []
    expected_prev = GENESIS_HASH

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue

            obj = json.loads(raw)

            prev_hash = obj.get("previous_hash")
            current_hash = obj.get("hash")
            payload = obj.get("payload")

            if prev_hash != expected_prev:
                raise ValueError(f"Hash chain broken at line {line_no} (prev mismatch)")

            canonical = _canonical_json(payload)
            recalculated = _sha256_hex(prev_hash + canonical)

            if recalculated != current_hash:
                raise ValueError(f"Hash mismatch at line {line_no}")

            payloads.append(payload)
            expected_prev = current_hash

    return payloads