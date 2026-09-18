# CSS Real-Environment Restore Drill Runbook

The repository provides:

    python scripts/run_css_production_restore_drill.py       --source-db <production-or-production-like-css-db>       --output-dir <isolated-evidence-directory>

Safety properties:
- source database is opened for backup/integrity validation but is never
  replaced by the script;
- backup and restore targets must be separate artifacts;
- checksum and SQLite integrity are verified;
- canonical migration/agreement tables are checked;
- a JSON evidence report is produced;
- successful drill output does not authorize production.

Before use in real production evidence:
- choose an encrypted evidence destination;
- preserve access/audit logs;
- document host/environment/operator;
- retain the generated SHA-256 and report;
- have the operations reviewer approve/reject the drill evidence.
