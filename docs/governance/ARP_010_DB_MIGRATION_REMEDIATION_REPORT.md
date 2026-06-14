# ARP-010 DB Migration and Session Initialization Remediation Report

## 1. Audit Finding

The post-remediation independent audit identified a high-severity runtime issue:

```text
sqlite3.OperationalError: no such table: sessions
```

The failure occurred when `TradeDecisionOrchestrator` initialized against a fresh SQLite database before session schema migrations had been applied.

## 2. Reproduction Steps

Command used before remediation:

```text
.venv\Scripts\python.exe -c "from pathlib import Path; import tempfile; from backend.app.persistence import db; db.close_connection(); db.DEFAULT_DB_PATH = Path(tempfile.mkdtemp()) / 'fresh_css_runtime.db'; print('DB_PATH', db.DEFAULT_DB_PATH); from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator; TradeDecisionOrchestrator()"
```

Pre-fix result:

```text
DB_PATH C:\Users\Larry\AppData\Local\Temp\tmpspyws31l\fresh_css_runtime.db
sqlite3.OperationalError: no such table: sessions
```

Failing path:

```text
backend.intelligence.trade_decision_orchestrator.TradeDecisionOrchestrator.__init__
  -> _initialize_runtime_session(...)
  -> SessionRepository.get_active_sessions()
  -> BaseRepository.fetch_all(...)
  -> sqlite3.OperationalError: no such table: sessions
```

## 3. Root Cause

The repository already contained migration ownership:

```text
backend/app/persistence/migrations/runner.py
backend/app/persistence/migrations/sql/001_sessions.sql
backend/app/persistence/migrations/sql/002_trades.sql
backend/app/persistence/migrations/sql/003_pnl_snapshots.sql
backend/app/persistence/migrations/sql/004_legal_acceptances.sql
```

However, `TradeDecisionOrchestrator` created and used `SessionRepository` through the persistence dependency chain without guaranteeing that migrations had run first. In a clean database, `SessionRepository.get_active_sessions()` queried the `sessions` table before it existed.

## 4. Files Reviewed

| File | Role |
| --- | --- |
| `backend/app/persistence/db.py` | SQLite connection owner. |
| `backend/app/persistence/migrations/runner.py` | Migration runner and schema migration table owner. |
| `backend/app/persistence/migrations/sql/001_sessions.sql` | Session and session history schema. |
| `backend/app/persistence/repositories/session_repository.py` | Durable session repository. |
| `backend/app/persistence/services/persistence_service.py` | Central persistence coordinator. |
| `backend/app/persistence/services/session_runtime_service.py` | Runtime session lifecycle service. |
| `backend/intelligence/trade_decision_orchestrator.py` | Orchestrator initialization path that exposed the gap. |
| `tests/test_security_phase_alpha.py` | Existing orchestrator/security test coverage. |
| `tests/governance/test_phase1_legal_acceptance_implementation.py` | Legal acceptance coverage. |

## 5. Files Changed

| File | Change |
| --- | --- |
| `backend/app/persistence/services/persistence_service.py` | Runs pending migrations during persistence service initialization before repositories are exposed. |
| `tests/test_session_schema_initialization.py` | Adds isolated clean-database tests for session schema bootstrap, orchestrator initialization, and legal acceptance persistence. |
| `docs/governance/ARP_010_DB_MIGRATION_REMEDIATION_REPORT.md` | Adds this remediation report. |
| `certification/security/SECURITY_CERTIFICATION_EVIDENCE_REGISTER.md` | References ARP-010 session initialization evidence. |
| `certification/governance/GOVERNANCE_CERTIFICATION_EVIDENCE_REGISTER.md` | References ARP-010 session governance evidence. |
| `certification/operations/OPERATIONS_CERTIFICATION_EVIDENCE_REGISTER.md` | References ARP-010 startup/session operations evidence. |

## 6. Remediation Approach

`PersistenceService.__init__()` now invokes:

```text
run_migrations()
```

before creating:

```text
SessionRepository
TradeRepository
PnlSnapshotRepository
LegalAcceptanceRepository
```

This uses the existing migration runner and SQL migration files rather than creating duplicate schema logic.

Safety properties:

* Legal acceptance enforcement is not bypassed.
* Authentication and RBAC are not bypassed.
* Database failures are not silently ignored; migration exceptions propagate.
* Broker adapters, dashboard behavior, strategy generation, credential handling, AntiBleedGuard, MarginTradeGate, live_toggle, live_arm, and unrelated execution logic were not changed.

## 7. Validation Results

Compile command:

```text
.venv\Scripts\python.exe -m py_compile backend\app\persistence\services\persistence_service.py tests\test_session_schema_initialization.py
```

Result:

```text
passed
```

Targeted session schema tests:

```text
.venv\Scripts\python.exe -m pytest tests\test_session_schema_initialization.py -q
```

Result:

```text
3 passed, 1 warning
```

Security tests:

```text
.venv\Scripts\python.exe -m pytest tests\test_security_phase_alpha.py -q
```

Result:

```text
8 passed
```

Legal acceptance tests:

```text
.venv\Scripts\python.exe -m pytest tests\governance\test_phase1_legal_acceptance_implementation.py -q
```

Result:

```text
8 passed
```

## 8. Remaining Risks

* Session runtime service still emits a non-failing `datetime.utcnow()` deprecation warning during the clean-database orchestrator test.
* This phase validates fresh SQLite schema bootstrap for targeted persistence/orchestrator paths; it does not replace a full runtime startup/shutdown certification run.
* Migration execution currently occurs when `PersistenceService` initializes. Direct manual use of low-level repositories without `PersistenceService` may still require callers to run migrations first unless future phases standardize repository-only bootstrap behavior.

## 9. Certification Impact

ARP-010 captures remediation evidence for clean-database session schema initialization. It supports security, governance, and operations certification evidence because legal acceptance orchestration can initialize required persistence tables without manual database intervention.

No certification evidence is marked approved. Robert review remains required.
