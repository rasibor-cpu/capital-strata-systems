from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.operations.backup_restore import (
    create_sqlite_backup,
    restore_sqlite_backup,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a non-destructive CSS production-environment backup/restore "
            "evidence drill. The source DB is never replaced."
        )
    )
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    backup = args.output_dir / f"css_backup_{stamp}.db"
    restored = args.output_dir / f"css_restore_{stamp}.db"

    artifact = create_sqlite_backup(
        source_path=args.source_db,
        backup_path=backup,
    )
    validation = restore_sqlite_backup(
        backup_path=backup,
        restored_path=restored,
        expected_backup_sha256=artifact.sha256,
        required_tables=(
            "schema_migrations",
            "commercial_agreement_snapshots",
        ),
    )

    report = {
        "source_db": str(args.source_db),
        "backup_path": artifact.backup_path,
        "backup_sha256": artifact.sha256,
        "backup_integrity": artifact.integrity_check,
        "backup_schema_version_count": artifact.schema_version_count,
        "restored_path": validation.restored_path,
        "restore_integrity": validation.integrity_check,
        "restore_schema_version_count": validation.schema_version_count,
        "required_tables_present": list(
            validation.required_tables_present
        ),
        "valid": validation.valid,
        "reason_codes": list(validation.reason_codes),
        "source_modified": False,
        "production_authorized": False,
    }
    report_path = args.output_dir / f"css_restore_drill_{stamp}.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**report, "report_path": str(report_path)}, indent=2))
    return 0 if validation.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
