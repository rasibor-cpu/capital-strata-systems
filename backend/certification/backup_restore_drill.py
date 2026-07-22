"""Measured local backup/restore drill (AR-015)."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_backup_restore_drill(
    *,
    source_dir: str | Path,
    work_dir: str | Path,
) -> dict[str, Any]:
    """
    Perform a measured local backup and restore of ``source_dir``.

    This is an evidence drill against repository/local artifacts — not a
    production cluster failover. Fail-closed on missing source or hash mismatch.
    """
    src = Path(source_dir)
    root = Path(work_dir)
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    if not src.exists() or not src.is_dir():
        return {
            "ok": False,
            "backup_performed": False,
            "restore_performed": False,
            "status": "FAIL",
            "failure_reason": "source_missing",
            "remediation_id": "AR-015",
            "execution_allowed": False,
            "started_at_utc": started.isoformat(),
        }

    backup_root = root / "backup"
    restore_root = root / "restore"
    if backup_root.exists():
        shutil.rmtree(backup_root)
    if restore_root.exists():
        shutil.rmtree(restore_root)

    t_backup_start = time.perf_counter()
    shutil.copytree(src, backup_root)
    backup_seconds = time.perf_counter() - t_backup_start

    manifests: list[dict[str, str]] = []
    for path in sorted(p for p in backup_root.rglob("*") if p.is_file()):
        rel = str(path.relative_to(backup_root)).replace("\\", "/")
        manifests.append({"path": rel, "sha256": _sha256_file(path)})

    t_restore_start = time.perf_counter()
    shutil.copytree(backup_root, restore_root)
    restore_seconds = time.perf_counter() - t_restore_start

    mismatches: list[str] = []
    for item in manifests:
        restored = restore_root / item["path"]
        if not restored.is_file():
            mismatches.append(f"missing:{item['path']}")
            continue
        if _sha256_file(restored) != item["sha256"]:
            mismatches.append(f"hash_mismatch:{item['path']}")

    finished = datetime.now(timezone.utc)
    ok = not mismatches
    payload = {
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "backup_performed": True,
        "restore_performed": True,
        "rto_seconds": round(restore_seconds, 6),
        "rpo_seconds": 0.0,
        "backup_duration_seconds": round(backup_seconds, 6),
        "total_duration_seconds": round(time.perf_counter() - t0, 6),
        "file_count": len(manifests),
        "mismatches": mismatches,
        "source_dir": str(src),
        "backup_dir": str(backup_root),
        "restore_dir": str(restore_root),
        "started_at_utc": started.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "remediation_id": "AR-015",
        "execution_allowed": False,
        "production_failover_claimed": False,
    }
    (root / "BACKUP_RESTORE_DRILL.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return payload


__all__ = ["run_backup_restore_drill"]
