# ARP-007 Non-Destructive Authority Quarantine Plan

## 1. Purpose

This document defines a non-destructive quarantine plan for duplicate or non-canonical CSS authority surfaces identified through ARP-006.

The goal is to reduce future audit ambiguity without deleting, moving, renaming, disabling, or modifying runtime authority files during this phase.

## 2. Scope

This phase covers quarantine planning for:

* CSSUnifiedTradeGate duplicates
* RiskGovernor duplicates
* Dashboard duplicate surfaces
* PnL authority duplicates
* Access control duplicates
* Build scripts containing live class definitions
* Historical dashboard versions

This phase is documentation-only. The only file created in ARP-007 is this governance report.

## 3. Canonical Authorities Preserved

The following authorities remain preserved as canonical or active support per ARP-006:

| Domain | Canonical / Preserved Authority | Status |
| --- | --- | --- |
| Backend unified trade gate | `backend/governance/css_unified_trade_gate.py` | KEEP_CANONICAL |
| Execution RiskGovernor | `engine/risk/risk_governor.py` | KEEP_CANONICAL |
| Current live dashboard | `scripts/css_live_dashboard.py` | KEEP_CANONICAL |
| Engine execution gate | `engine/execution/execution_gate.py` | KEEP_CANONICAL |
| AntiBleedGuard | `backend/app/risk/anti_bleed_guard.py` | KEEP_CANONICAL |
| MarginTradeGate | `engine/risk/margin_trade_gate.py` | KEEP_CANONICAL |
| Engine PnL tracking | `engine/performance/pnl_tracker.py` | KEEP_CANONICAL |
| Dashboard open-position authority | `scripts/css_live_dashboard.py` `MarkToMarketEngine` | KEEP_CANONICAL |
| Accounting PnL observer | `backend/app/accounting/pnl_engine.py` | KEEP_ACTIVE_SUPPORT |
| Legal acceptance authority | `backend/app/compliance/legal_acceptance.py`; `backend/app/compliance/legal_acceptance_service.py`; `backend/app/compliance/legal_acceptance_enforcement.py` | KEEP_CANONICAL |
| live_toggle authorization | `backend/app/security/live_toggle.py` | KEEP_CANONICAL |
| live_arm state | `backend/app/ops/live_arm.py` | KEEP_CANONICAL |

## 4. Duplicate Authority Surfaces

Duplicate authority surfaces are files or modules that contain names, classes, functions, or behavior similar to canonical authorities but are not the current primary runtime authority.

These files are not necessarily harmful by existence alone. The risk is that future maintainers, scripts, tests, or audits may confuse them for canonical implementations.

## 5. Quarantine Candidates

Quarantine candidates should be marked, cataloged, or moved in a future phase only after test proof confirms they are not active runtime authorities.

Recommended non-destructive quarantine pattern for future phases:

1. Add governance headers stating the file is non-canonical.
2. Add import/path tests proving canonical imports remain unchanged.
3. Move historical files to a clearly labeled archive path only after Robert approval.
4. Retain audit traceability for every move or retirement.
5. Avoid deleting files until a separate removal phase proves no references remain.

## 6. Retirement Candidates

Retirement candidates are duplicate or generated authority surfaces that should be reviewed for future removal or archival, but not in ARP-007.

Priority retirement candidates:

* `css_live_dashboard_v5.py`
* `scripts/build_r7_unified_trade_gate.py`
* `scripts/build_r*.py` dashboard generation lineage scripts that contain or emit runtime authority code
* `scripts/css_live_dashboard_PRE_J7_BACKUP.py`
* `scripts/css_live_dashboard_BACKUP_BEFORE_COINBASE_BALANCE_FIX.py`
* Legacy `RiskGovernor` implementations in `backend/app/...`
* Legacy backend PnL modules under `backend/app/pnl/...`
* Historical dashboard versions in `archive/dashboard_versions/...`

## 7. No-Delete Policy

ARP-007 makes no destructive changes.

Guardrails:

* No files were deleted.
* No files were moved.
* No files were renamed.
* No imports were changed.
* No runtime behavior changed.
* No dashboard behavior changed.
* No tests were changed.
* No broker adapters were changed.
* No credentials were changed.
* No archive files were modified.

Future retirement requires a separate phase, Robert approval, and test proof that runtime imports and behavior remain intact.

## 8. Future Implementation Steps

Recommended future implementation sequence:

1. Create an authority import regression test that asserts canonical imports resolve to expected files.
2. Add non-canonical warning headers to duplicate authority files without changing behavior.
3. Create an archive movement proposal listing every file to move and every reference to update.
4. Run targeted and affected test suites before and after any movement.
5. Move duplicate files to an approved archive/quarantine location in a separate non-runtime phase.
6. Remove only after a later phase proves zero runtime, test, script, and documentation dependencies.

## 9. Validation Requirements

Future quarantine or retirement phases must validate:

* `backend/governance/css_unified_trade_gate.py` remains the canonical backend `CSSUnifiedTradeGate`.
* `engine/risk/risk_governor.py` remains the canonical execution `RiskGovernor`.
* `scripts/css_live_dashboard.py` remains the canonical live dashboard.
* `engine/execution/execution_gate.py` still enforces AntiBleedGuard and MarginTradeGate.
* Dashboard tests that load `scripts/css_live_dashboard.py` still pass.
* Broker adapter tests still pass if any broker-facing path is affected.
* No live trading behavior is enabled or weakened.
* No credential-loading behavior changes.

No tests are required for ARP-007 itself because it is documentation-only.

## 10. Risk Notes

Key risks if duplicate authorities remain unmarked:

* Future audits may count legacy copies as active runtime authorities.
* Maintainers may patch a legacy implementation instead of the canonical authority.
* Clean-clone validation may execute legacy scripts with direct missing imports.
* Generated dashboard lineage scripts may reintroduce old authority code.
* Duplicate access-control modules may create confusion between backend, app, and engine security layers.
* Duplicate PnL surfaces may be mistaken for competing authorities rather than domain-specific runtime, dashboard, accounting, persistence, and reporting surfaces.

Key risks if cleanup is rushed:

* Import paths may break silently.
* Historical reproducibility may be lost.
* Dashboard scripts may lose operator fallback context.
* Tests that intentionally load old surfaces may fail without replacement.
* Audit traceability may become weaker rather than stronger.

## 11. Classification Table

| File | Domain | Current Classification | Proposed Action | Reason | Runtime Impact |
| ------ | ------ | ------ | ------ | ------ | ------ |
| `backend/governance/css_unified_trade_gate.py` | CSSUnifiedTradeGate | CANONICAL | KEEP_CANONICAL | Backend trade decision and live readiness authority. | Preserve. |
| `scripts/css_live_dashboard.py` local `CSSUnifiedTradeGate` | CSSUnifiedTradeGate / Dashboard | ACTIVE_SUPPORT | KEEP_ACTIVE_SUPPORT | Dashboard-local pre-register gate; not backend authority. | Preserve until dashboard architecture changes. |
| `scripts/build_r7_unified_trade_gate.py` | CSSUnifiedTradeGate / Build script | RETIREMENT_CANDIDATE | MARK_RETIREMENT_CANDIDATE | Contains live class definition in build/insertion script. | No current runtime impact if not executed. |
| `scripts/css_live_dashboard_PRE_J7_BACKUP.py` | CSSUnifiedTradeGate / Dashboard backup | LEGACY | MARK_LEGACY | Backup dashboard copy with duplicate gate. | No canonical runtime impact. |
| `scripts/css_live_dashboard_BACKUP_BEFORE_COINBASE_BALANCE_FIX.py` | CSSUnifiedTradeGate / Dashboard backup | LEGACY | MARK_LEGACY | Backup dashboard copy with duplicate gate. | No canonical runtime impact. |
| `archive/dashboard_versions/...` | CSSUnifiedTradeGate / Historical dashboards | ARCHIVE | MARK_ARCHIVE | Historical dashboard copies. | No active runtime impact. |
| `engine/risk/risk_governor.py` | RiskGovernor | CANONICAL | KEEP_CANONICAL | Imported by `ExecutionGate` and runtime tests. | Preserve. |
| `backend/app/risk_governor.py` | RiskGovernor | LEGACY | MARK_LEGACY | Duplicate governor not used by canonical `ExecutionGate`. | No known canonical runtime impact. |
| `backend/app/risk/risk_governor.py` | RiskGovernor | LEGACY | MARK_LEGACY | Duplicate nested backend app governor. | No known canonical runtime impact. |
| `backend/app/engine_risk.py` | RiskGovernor / Engine risk | LEGACY | MARK_LEGACY | Older engine-risk surface with duplicate governor. | No known canonical runtime impact. |
| `backend/risk/portfolio_risk_governor.py` | Portfolio risk governor | LEGACY | MARK_LEGACY | Used by older backend engine path only. | Could affect legacy backend engine if executed. |
| `css_live_dashboard_v5.py` | Dashboard | RETIREMENT_CANDIDATE | MARK_RETIREMENT_CANDIDATE | Root dashboard has duplicate `display_dashboard` and `execute_trade` definitions plus direct missing data import. | Risk if manually executed; not canonical. |
| `scripts/css_live_dashboard.py` | Dashboard | CANONICAL | KEEP_CANONICAL | Current live dashboard authority and target of recent tests. | Preserve. |
| `scripts/css_live_dashboard_PRE_J7_BACKUP.py` | Dashboard backup | LEGACY | FUTURE_MOVE_TO_ARCHIVE | Backup script may confuse audits. | No canonical runtime impact. |
| `scripts/css_live_dashboard_BACKUP_BEFORE_COINBASE_BALANCE_FIX.py` | Dashboard backup | LEGACY | FUTURE_MOVE_TO_ARCHIVE | Backup script may confuse audits. | No canonical runtime impact. |
| `scripts/build_r*.py` | Dashboard build lineage | RETIREMENT_CANDIDATE | MARK_RETIREMENT_CANDIDATE | Build scripts contain historical output paths and may emit old dashboard authority code. | No runtime impact unless executed. |
| `archive/dashboard_versions/...` | Historical dashboards | ARCHIVE | MARK_ARCHIVE | Historical dashboard versions should remain archive-only. | No active runtime impact. |
| `engine/performance/pnl_tracker.py` | PnL | CANONICAL | KEEP_CANONICAL | Engine loop equity/PnL tracker. | Preserve. |
| `scripts/css_live_dashboard.py` `MarkToMarketEngine` | PnL / Dashboard open positions | CANONICAL | KEEP_CANONICAL | Runtime dashboard open-position authority. | Preserve. |
| `scripts/css_live_dashboard.py` `append_closed_trade_ledger(...)` | PnL / Dashboard closed ledger | ACTIVE_SUPPORT | KEEP_ACTIVE_SUPPORT | Closed-trade ledger support. | Preserve. |
| `backend/app/accounting/pnl_engine.py` | PnL accounting observer | ACTIVE_SUPPORT | KEEP_ACTIVE_SUPPORT | Accounting snapshot/observer path. | Preserve. |
| `backend/app/persistence/repositories/pnl_snapshot_repository.py` | PnL persistence | ACTIVE_SUPPORT | KEEP_ACTIVE_SUPPORT | Durable PnL snapshot persistence. | Preserve. |
| `backend/app/persistence/services/pnl_runtime_service.py` | PnL persistence service | ACTIVE_SUPPORT | KEEP_ACTIVE_SUPPORT | Runtime persistence service for PnL snapshots. | Preserve. |
| `engine/reporting/pnl_ledger.py` | PnL reporting | ACTIVE_SUPPORT | KEEP_ACTIVE_SUPPORT | Reporting/test ledger support. | Preserve. |
| `engine/reporting/pnl_report.py` | PnL reporting | ACTIVE_SUPPORT | KEEP_ACTIVE_SUPPORT | Reporting summaries. | Preserve. |
| `backend/app/pnl/...` | PnL legacy | LEGACY | MARK_LEGACY | Legacy backend PnL surface. | No known canonical runtime impact. |
| `engine/security/access_control.py` | Access control | CANONICAL / ACTIVE_SUPPORT | KEEP_ACTIVE_SUPPORT | Engine security access-control layer. | Preserve. |
| `backend/security/access_control.py` | Access control | ACTIVE_SUPPORT | KEEP_ACTIVE_SUPPORT | Backend security access-control layer. | Preserve. |
| `backend/app/security/access_control.py` | Access control | ACTIVE_SUPPORT | KEEP_ACTIVE_SUPPORT | App module-level permission enforcement. | Preserve. |
| `backend/app/security/auth_gate_PRE_PACK4.py` | Authentication / Access control | LEGACY | MARK_LEGACY | Pre-pack backup auth gate. | No canonical runtime impact. |
| `backend/app/security/user_registry_PRE_PACK4.py` | Authentication / User registry | LEGACY | MARK_LEGACY | Pre-pack backup user registry. | No canonical runtime impact. |
| `backend/scanner/unified_market_scanner.py` | Dashboard data/import support | ACTIVE_SUPPORT | KEEP_ACTIVE_SUPPORT | Has safe fallback for missing Coinbase data module. | Preserve. |
| `scripts/css_extended_paper_test.py` | Dashboard/data test script | ACTIVE_SUPPORT / RETIREMENT_CANDIDATE | MARK_RETIREMENT_CANDIDATE | Direct import of ignored/non-tracked Coinbase data module. | Risk if executed in clean clone. |
| `backend/data/coinbase_historical_downloader.py` | Data dependency | NON_TRACKED / IGNORED | FUTURE_REMOVE_AFTER_TEST_PROOF or restore intentionally | Referenced by some direct-import consumers but ignored by `data/` rule. | Must be resolved before direct-import consumers are kept. |

## 12. Proposed Action Definitions

| Proposed Action | Meaning |
| --- | --- |
| KEEP_CANONICAL | Preserve as the authoritative implementation. |
| KEEP_ACTIVE_SUPPORT | Preserve as an active support surface with documented boundaries. |
| MARK_LEGACY | Add future non-runtime/legacy marker without moving or deleting. |
| MARK_ARCHIVE | Preserve as archive-only historical evidence. |
| MARK_RETIREMENT_CANDIDATE | Flag for future retirement review with import and test proof. |
| FUTURE_MOVE_TO_ARCHIVE | Move only in a later approved phase after references are proven safe. |
| FUTURE_REMOVE_AFTER_TEST_PROOF | Remove only in a later approved phase after zero-dependency proof and Robert approval. |

## 13. ARP-007 Guardrail Confirmation

ARP-007 confirms:

* No files were deleted.
* No files were moved.
* No files were renamed.
* No imports were changed.
* No runtime behavior changed.
* No dashboard behavior changed.
* No broker behavior changed.
* No execution behavior changed.
* No risk behavior changed.
* No margin behavior changed.
* No security behavior changed.
* No strategy behavior changed.
* No tests were changed.
* No credentials were changed.
* Future retirement requires a separate phase and test proof.

Robert must review before any destructive cleanup phase begins.
