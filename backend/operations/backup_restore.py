from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True, slots=True)
class BackupArtifact:
    source_path: str
    backup_path: str
    sha256: str
    integrity_check: str
    schema_version_count: int


@dataclass(frozen=True, slots=True)
class RestoreValidation:
    restored_path: str
    backup_sha256: str
    restored_sha256: str
    integrity_check: str
    schema_version_count: int
    required_tables_present: Tuple[str, ...]
    valid: bool
    reason_codes: Tuple[str, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity_check(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA integrity_check;").fetchone()
    return str(row[0] if row else "missing")


def create_sqlite_backup(
    *,
    source_path: Path,
    backup_path: Path,
) -> BackupArtifact:
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    if source_path.resolve() == backup_path.resolve():
        raise ValueError("backup path must differ from source path")

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if backup_path.exists():
        backup_path.unlink()

    source = sqlite3.connect(source_path)
    try:
        integrity = _integrity_check(source)
        if integrity.lower() != "ok":
            raise RuntimeError(
                f"source database integrity check failed: {integrity}"
            )
        source.execute("PRAGMA wal_checkpoint(FULL);")
        target = sqlite3.connect(backup_path)
        try:
            source.backup(target)
            target.commit()
        finally:
            target.close()
    finally:
        source.close()

    verify = sqlite3.connect(backup_path)
    try:
        backup_integrity = _integrity_check(verify)
        if backup_integrity.lower() != "ok":
            raise RuntimeError(
                f"backup database integrity check failed: {backup_integrity}"
            )
        row = verify.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()
        schema_count = int(row[0]) if row else 0
    finally:
        verify.close()

    return BackupArtifact(
        source_path=str(source_path),
        backup_path=str(backup_path),
        sha256=_sha256(backup_path),
        integrity_check=backup_integrity,
        schema_version_count=schema_count,
    )


def restore_sqlite_backup(
    *,
    backup_path: Path,
    restored_path: Path,
    expected_backup_sha256: str,
    required_tables: Tuple[str, ...] = (),
) -> RestoreValidation:
    reasons: list[str] = []

    if not backup_path.exists():
        return RestoreValidation(
            restored_path=str(restored_path),
            backup_sha256="",
            restored_sha256="",
            integrity_check="missing",
            schema_version_count=0,
            required_tables_present=(),
            valid=False,
            reason_codes=("BACKUP_MISSING",),
        )

    backup_sha = _sha256(backup_path)
    if backup_sha != expected_backup_sha256:
        reasons.append("BACKUP_CHECKSUM_MISMATCH")

    try:
        source = sqlite3.connect(backup_path)
        try:
            source_integrity = _integrity_check(source)
            if source_integrity.lower() != "ok":
                reasons.append("BACKUP_INTEGRITY_FAILED")
        finally:
            source.close()
    except sqlite3.DatabaseError:
        return RestoreValidation(
            restored_path=str(restored_path),
            backup_sha256=backup_sha,
            restored_sha256="",
            integrity_check="corrupt",
            schema_version_count=0,
            required_tables_present=(),
            valid=False,
            reason_codes=tuple(reasons + ["BACKUP_DATABASE_CORRUPT"]),
        )

    if reasons:
        return RestoreValidation(
            restored_path=str(restored_path),
            backup_sha256=backup_sha,
            restored_sha256="",
            integrity_check=source_integrity,
            schema_version_count=0,
            required_tables_present=(),
            valid=False,
            reason_codes=tuple(reasons),
        )

    restored_path.parent.mkdir(parents=True, exist_ok=True)
    if restored_path.exists():
        restored_path.unlink()

    source = sqlite3.connect(backup_path)
    target = sqlite3.connect(restored_path)
    try:
        source.backup(target)
        target.commit()
    finally:
        target.close()
        source.close()

    restored_sha = _sha256(restored_path)
    conn = sqlite3.connect(restored_path)
    try:
        integrity = _integrity_check(conn)
        if integrity.lower() != "ok":
            reasons.append("RESTORE_INTEGRITY_FAILED")

        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        present = tuple(
            table for table in required_tables if table in tables
        )
        missing = [
            table for table in required_tables if table not in tables
        ]
        if missing:
            reasons.append(
                "RESTORE_REQUIRED_TABLES_MISSING:" + ",".join(missing)
            )

        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM schema_migrations"
            ).fetchone()
            schema_count = int(row[0]) if row else 0
        except sqlite3.DatabaseError:
            schema_count = 0
            reasons.append("RESTORE_SCHEMA_MIGRATIONS_MISSING")
    finally:
        conn.close()

    return RestoreValidation(
        restored_path=str(restored_path),
        backup_sha256=backup_sha,
        restored_sha256=restored_sha,
        integrity_check=integrity,
        schema_version_count=schema_count,
        required_tables_present=present,
        valid=not reasons,
        reason_codes=tuple(reasons),
    )
