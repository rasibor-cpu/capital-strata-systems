# CSS Production-Readiness Technical Drill Matrix

Status: INTERNAL TECHNICAL EVIDENCE — EXTERNAL PRODUCTION APPROVALS NOT IMPLIED
Date: 2026-09-16

## Purpose

This drill closes the internally provable recovery, rollback, reconciliation,
security and integration controls that remain after accepted UAT Cycle 1.

## Technical drill areas

| Area | Acceptance criterion | Evidence |
| --- | --- | --- |
| Backup integrity | Known-good SQLite state backs up with integrity_check=ok and SHA-256 evidence. | tests/test_production_backup_restore_drill.py |
| Restore integrity | Backup restores to an isolated path with required canonical tables and migration history intact. | tests/test_production_backup_restore_drill.py |
| Tamper detection | Modified backup checksum blocks restore. | tests/test_production_backup_restore_drill.py |
| Corrupt-store handling | Invalid SQLite backup fails closed and does not create a restored runtime store. | tests/test_production_backup_restore_drill.py |
| Rollback | Restored snapshot contains pre-change state and excludes post-snapshot state. | tests/test_production_backup_restore_drill.py |
| Restart persistence | Canonical agreement survives connection close/reopen. | tests/test_uat_restart_persistence.py |
| Startup reconciliation | Broker/local mismatch or broker error locks the session. | tests/scripts/test_startup_reconciliation.py |
| Continuous reconciliation | Runtime divergence/API failure locks the session. | tests/scripts/test_continuous_reconciliation.py |
| Post-trade reconciliation | Missing/mismatched broker trade locks the session. | tests/scripts/test_post_trade_reconciliation.py |
| Runtime health | Operational state remains observable and safe-fail. | tests/test_runtime_health_provider.py |
| Security certification model | Missing security control prevents production security readiness. | tests/test_production_security_and_payment_provider.py |
| Provider persistence | Security/provider configuration persists canonically. | tests/test_production_infrastructure_persistence.py |
| Broker mutation boundary | OANDA execution remains behind canonical RBAC/live-arm controls, idempotency and unit ceiling. | tests/test_security_phase_alpha.py |
| Customer/operator web | Required pages/API routes/disclosures coexist under current FastAPI/Starlette. | dashboard/web/web_smoke_test.py |
| Integrated RC safety | Sandbox UAT/dossier/payment/notification are green while production and external money movement stay blocked. | scripts/run_css_full_test_readiness.py |

## Acceptance boundary

Passing this drill means the software has executable evidence for the listed
technical controls in an isolated controlled environment.

It does not provide:

- legal/regulatory approval;
- production broker/payment/notification credentials;
- live provider settlement evidence;
- actual warm-standby infrastructure;
- off-site backup infrastructure;
- production incident-response exercise evidence; or
- authorized production release-owner sign-off.

Those remain external/environmental evidence requirements.
