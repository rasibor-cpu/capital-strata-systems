# CSS Repository Reconciliation Report

Date: 2026-05-12  
Project: Capital Strata Systems (CSS)  
Scope: Repository reconciliation and implementation gap analysis  
Commit inspected: `4593019 PCNRASS: add broker balance reconciliation`  
Branch inspected: `css-must-haves-phase1-2026-05-12`

## Executive Summary

Repository reconciliation was completed without code changes, staging, or commits.

The current runtime/dashboard smoke-test layer remains stable. However, full institutional readiness is not confirmed because the intelligence orchestrator and broker bootstrap paths currently fail validation.

The repository also has a documentation synchronization issue: authoritative governance documents exist on `origin/main`, while the local working branch does not yet contain those commits.

## Current Repository State

- Current branch: `css-must-haves-phase1-2026-05-12`
- Current commit: `4593019`
- Local `main` also points to `4593019`
- `origin/main` is ahead with recent governance/documentation commits
- Pre-existing dirty item: `CSS-CLAUDE`
- `CSS-CLAUDE` was not inspected or modified
- No files were changed during reconciliation
- No commit was created

## Implementation Status Matrix

| Component | Status | Confidence | Notes |
|---|---:|---:|---|
| Governance docs on GitHub | PARTIAL | HIGH | Authoritative on `origin/main`, not yet present locally |
| DashboardState/runtime contracts | WORKING | HIGH | Payload, API, and smoke tests pass |
| Legacy dashboard script | DUPLICATED | HIGH | `scripts/css_live_dashboard.py` still contains business and trading logic |
| Web dashboard WebSocket sync | PARTIAL | HIGH | Server emits typed events, web client still expects `dashboard_delta` |
| Mobile app | PARTIAL | HIGH | Smoke tests pass; session storage is still in-memory |
| TradeDecisionOrchestrator | BROKEN | HIGH | Constructor fails due `CapitalAllocator(total_capital)` mismatch |
| Engine intelligence orchestrator | BROKEN | HIGH | Imports missing `TradeDecisionEngine` symbol |
| CSSUnifiedTradeGate | PARTIAL | HIGH | Core gate works; persistent audit wiring is incomplete |
| Broker bootstrap | BROKEN | HIGH | Imports missing `backend.app.brokers.broker_registry` |
| Coinbase integration | PARTIAL | HIGH | Split across adapter, executor, and mobile paths |
| OANDA integration | PARTIAL | MEDIUM | Adapter exists; central broker bootstrap path is broken |
| IBKR integration | COSMETIC_ONLY | HIGH | Product coverage registry exists; no live adapter/execution path |
| Broker capabilities | PARTIAL | HIGH | Registry does not fully cover Coinbase, OANDA, IBKR, and live variants |
| Broker balance reconciliation | WORKING | HIGH | Snapshot reconciliation tests pass |
| PnL/accounting | PARTIAL | MEDIUM | Canonical ledger exists; dashboard summaries derive from position state |
| Audit viewer/replay harness | PARTIAL | MEDIUM | Implemented, but not all systems feed one unified audit trail |
| Auth/RBAC | PARTIAL | HIGH | Sign-on smoke passes; file-based users and in-memory sessions remain |
| Secret exclusion | WORKING | HIGH | `.env`, keys, audit logs, and artifacts are ignored |
| Asset-class expansion | PARTIAL | HIGH | Active routing supports core classes; broader IBKR catalog is registry-only |

## Broken Or Missing Integrations

1. `backend/intelligence/trade_decision_orchestrator.py`
   - Fails at construction because `CapitalAllocator` now requires `total_capital`.

2. `backend/engine/intelligence_orchestrator.py`
   - Imports missing `TradeDecisionEngine`.

3. `backend/app/brokers/broker_bootstrap.py`
   - References a missing broker registry module in the expected package path.

4. `dashboard/web/web_app.py`
   - WebSocket handler does not consume the typed events emitted by `dashboard/runtime/ws_bridge.py`.

5. IBKR execution integration
   - Current implementation is product coverage/catalog level only.
   - No executable IBKR broker adapter was confirmed.

## Risk Areas

- Local branch drift from authoritative governance documents on `origin/main`
- Duplicate execution, broker, accounting, risk, session, and audit paths
- Legacy dashboard script still containing business logic
- Split Coinbase behavior across multiple modules
- Incomplete broker bootstrap and broker capability enforcement
- Incomplete WebSocket frontend migration
- Dashboard PnL not fully proven as canonical ledger-derived
- In-memory session storage in mobile/backend paths
- IBKR product coverage not yet connected to live broker execution

## Cosmetic-Only Areas

- IBKR integration is currently registry/catalog level, not executable broker integration.
- Some dashboard surfaces are smoke-tested and contract-fed, but older dashboard paths still simulate or render values outside the canonical runtime bridge.

## Duplicate Systems And Modules

Notable duplication exists around:

- PnL engines: `engine/ledger` and `backend/app/accounting`
- Risk governors: `engine/risk`, `backend/app/risk`, and related app-level risk modules
- Broker registries and bootstrap paths
- Session managers across dashboard auth, mobile sessions, and backend security
- Audit systems across security audit ledger, governance audit logger, replay artifacts, and runtime audit viewer

## Validation Commands Executed

The following validation classes were executed:

```powershell
.\.venv\Scripts\python.exe -m py_compile ...
```

Result: passed.

```powershell
.\.venv\Scripts\python.exe -m pytest tests\dashboard\... tests\engine\... -q
```

Result: `46 passed`.

```powershell
$env:PYTHONPATH='.'; .\.venv\Scripts\python.exe dashboard\runtime\runtime_smoke_test.py
$env:PYTHONPATH='.'; .\.venv\Scripts\python.exe dashboard\web\web_smoke_test.py
$env:PYTHONPATH='.'; .\.venv\Scripts\python.exe dashboard\auth\css_sign_on_smoke_test.py
$env:PYTHONPATH='.'; .\.venv\Scripts\python.exe dashboard\mobile\mobile_smoke_test.py
```

Result: all passed.

## Failed Validations

```powershell
TradeDecisionOrchestrator smoke
```

Result:

```text
TypeError: CapitalAllocator.__init__() missing required total_capital
```

```powershell
backend.engine.intelligence_orchestrator import
```

Result:

```text
cannot import name TradeDecisionEngine
```

```powershell
backend.app.brokers.broker_bootstrap import
```

Result:

```text
ModuleNotFoundError: No module named 'backend.app.brokers.broker_registry'
```

## Recommended Next Priorities

1. Sync or merge the authoritative governance documents from `origin/main`.
2. Fix the orchestrator constructor and stale intelligence import.
3. Repair broker bootstrap and broker registry package layout.
4. Update web/mobile clients to consume typed WebSocket events.
5. Consolidate broker capability, broker mode, and asset validation into one fail-closed route.
6. Align dashboard PnL more explicitly to canonical ledger authority.
7. Move sessions and users toward persistent institutional storage.
8. Add release checklist automation that proves PCNRASS before every push.

## Recommended Future Commit Message

```text
PCNRASS: reconcile implementation gaps and repair orchestrator bootstrap
```

## PCNRASS Status

PCNRASS is partially confirmed:

- Runtime/dashboard smoke stability is confirmed based on listed checks.
- Full institutional readiness is not confirmed because orchestrator and broker bootstrap validations currently fail.

