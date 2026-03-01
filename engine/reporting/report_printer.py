"""
Capital Strata Systems (CSS)
Phase 23.3 — Immutable EOD Snapshot Pack Engine

Purpose:
- Persist EOD reports into date-partitioned folder
- Generate per-file SHA256 hash
- Generate pack-level integrity hash
- Produce manifest.json for audit retrieval
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


EOD_ROOT = Path("audit_logs/eod_packs")


# ============================================================
# Utilities
# ============================================================

def _now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_file(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    path.write_bytes(data)
    return _sha256_bytes(data)


# ============================================================
# EOD Pack Generator
# ============================================================

def generate_eod_pack(
    *,
    run_date: str,
    trial_balance: Dict[str, Any],
    dormancy_summary: Dict[str, Any],
    accrual_summary: Dict[str, Any],
) -> Dict[str, Any]:

    pack_dir = EOD_ROOT / run_date
    pack_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_date": run_date,
        "generated_at": _now(),
        "files": [],
    }

    # --------------------------------------------------------
    # Trial Balance
    # --------------------------------------------------------
    tb_path = pack_dir / "trial_balance.txt"
    tb_hash = _write_file(tb_path, trial_balance.get("content", ""))

    manifest["files"].append({
        "file": "trial_balance.txt",
        "sha256": tb_hash,
    })

    # --------------------------------------------------------
    # Dormancy Summary
    # --------------------------------------------------------
    dorm_path = pack_dir / "dormancy_summary.json"
    dorm_hash = _write_file(dorm_path, json.dumps(dormancy_summary, indent=2))

    manifest["files"].append({
        "file": "dormancy_summary.json",
        "sha256": dorm_hash,
    })

    # --------------------------------------------------------
    # Accrual Summary
    # --------------------------------------------------------
    accr_path = pack_dir / "accrual_summary.json"
    accr_hash = _write_file(accr_path, json.dumps(accrual_summary, indent=2))

    manifest["files"].append({
        "file": "accrual_summary.json",
        "sha256": accr_hash,
    })

    # --------------------------------------------------------
    # Manifest
    # --------------------------------------------------------
    manifest_path = pack_dir / "manifest.json"
    manifest_hash = _write_file(manifest_path, json.dumps(manifest, indent=2))

    # --------------------------------------------------------
    # Pack Integrity Hash
    # --------------------------------------------------------
    combined_hash_input = "".join([f["sha256"] for f in manifest["files"]])
    pack_hash = hashlib.sha256(combined_hash_input.encode("utf-8")).hexdigest()

    integrity_path = pack_dir / "pack_integrity.sha256"
    integrity_path.write_text(pack_hash, encoding="utf-8")

    return {
        "ok": True,
        "run_date": run_date,
        "pack_hash": pack_hash,
        "files_written": len(manifest["files"]),
    }