# ARP-003 Authority Consolidation Verification Report

## 1. Purpose

This report documents the ARP-003 authority consolidation verification for the partially verified audit findings from the CSS Audit Remediation Program.

This phase is documentation-only. No runtime, broker, execution, dashboard, risk, margin, security, credential, or trading logic changes were made.

## 2. Pre-Check

Repository remote:

```text
origin  https://github.com/rasibor-cpu/capital-strata-systems.git (fetch)
origin  https://github.com/rasibor-cpu/capital-strata-systems.git (push)
```

Branch:

```text
css-evening-consolidation-2026-06-09
```

HEAD before ARP-003 documentation changes:

```text
d5f725c6247d48f024c3d85b702c643ac7096535
```

## 3. Verification Scope

Findings reviewed:

| Finding | Scope | Current Classification |
| --- | --- | --- |
| B-03 | Dashboard duplicate authorities | PARTIALLY VERIFIED |
| B-06 | BOM / syntax findings | PARTIALLY VERIFIED |
| B-07 | Multiple CSSUnifiedTradeGate definitions | VERIFIED |
| B-08 | Multiple RiskGovernor definitions | VERIFIED |
| B-10 | Dashboard import issue | PARTIALLY VERIFIED |

Authority classifications used:

| Classification | Meaning |
| --- | --- |
| CANONICAL | Implementation currently authoritative for the primary runtime path. |
| ACTIVE_SUPPORT | Active helper or support implementation used by an operational script or adapter, but not the canonical backend authority. |
| LEGACY | Older implementation retained in tracked code with limited or unclear active runtime authority. |
| ARCHIVE | Archived implementation outside current authority. |
| RETIREMENT_CANDIDATE | Duplicate or generated implementation that should be consolidated or removed in a later remediation phase after review. |

## 4. CSSUnifiedTradeGate Authority Analysis

### Definitions Identified

| File | Evidence | Classification |
| --- | --- | --- |
| `backend/governance/css_unified_trade_gate.py` | Defines `class CSSUnifiedTradeGate` at line 41. | CANONICAL |
| `scripts/css_live_dashboard.py` | Defines a dashboard-local `class CSSUnifiedTradeGate` at line 1926 and instantiates `css_unified_trade_gate` at line 1965. | ACTIVE_SUPPORT |
| `scripts/build_r7_unified_trade_gate.py` | Defines `class CSSUnifiedTradeGate` at line 9 as a build/insertion script. | RETIREMENT_CANDIDATE |
| `scripts/css_live_dashboard_PRE_J7_BACKUP.py` | Defines `class CSSUnifiedTradeGate` at line 1605. | LEGACY |
| `scripts/css_live_dashboard_BACKUP_BEFORE_COINBASE_BALANCE_FIX.py` | Defines `class CSSUnifiedTradeGate` at line 1598. | LEGACY |
| `archive/dashboard_versions/...` | Multiple archived dashboard copies define `CSSUnifiedTradeGate`. | ARCHIVE |

### Import and Runtime Relationships

Canonical backend imports:

* `backend/intelligence/trade_decision_orchestrator.py` imports `CSSUnifiedTradeGate` from `backend.governance.css_unified_trade_gate` and instantiates it as `self.trade_gate`.
* `backend/app/brokers/live_readiness_certifier.py` imports `CSSUnifiedTradeGate` from `backend.governance.css_unified_trade_gate` and instantiates it during live readiness certification.
* `tests/test_security_phase_alpha.py` imports `CSSUnifiedTradeGate` from `backend.governance.css_unified_trade_gate`.

Dashboard-local usage:

* `scripts/css_live_dashboard.py` contains a local `CSSUnifiedTradeGate` implementation used by `approve_trade_before_register(...)`.
* This dashboard-local gate is active only inside the dashboard script and does not replace the backend canonical gate.

### Authoritative Runtime Determination

The authoritative backend trade decision implementation is:

```text
backend/governance/css_unified_trade_gate.py
```

The dashboard-local implementation in `scripts/css_live_dashboard.py` is an active support authority for dashboard-driven pre-position registration checks, but it is not the canonical backend authority imported by the orchestrator or live readiness certifier.

### Duplicate Runtime Impact

The duplicates affect runtime behavior only when their specific script is executed. The backend canonical execution decision path uses `backend.governance.css_unified_trade_gate.CSSUnifiedTradeGate`.

The build script and backup dashboard copies create governance ambiguity and should be consolidated or explicitly retired in a later remediation phase.

## 5. RiskGovernor Authority Analysis

### Implementations Identified

| File | Evidence | Classification |
| --- | --- | --- |
| `engine/risk/risk_governor.py` | Defines `class RiskGovernor` at line 70. | CANONICAL |
| `backend/app/engine_risk.py` | Defines `class RiskGovernor` at line 46. | LEGACY |
| `backend/app/risk_governor.py` | Defines `class RiskGovernor` at line 14. | LEGACY |
| `backend/app/risk/risk_governor.py` | Defines `class RiskGovernor` at line 16. | LEGACY |

### Import and Runtime Relationships

Canonical imports and usage:

* `engine/execution/execution_gate.py` imports `RiskGovernor` from `engine.risk.risk_governor` and instantiates it inside `ExecutionGate`.
* `tests/engine/test_risk_governor.py` imports `RiskGovernor` from `engine.risk.risk_governor`.
* `run_sim_close.py` imports `RiskGovernor` from `engine.risk.risk_governor`.
* `backend/app/run_live_guarded.py` imports `RiskGovernor` from `engine.risk.risk_governor`.

No active non-archive import evidence was found for the three `backend/app/...` duplicate `RiskGovernor` classes during this verification pass.

### Authoritative Runtime Determination

The authoritative RiskGovernor for current execution gate decisions is:

```text
engine/risk/risk_governor.py
```

### Duplicate Runtime Impact

The duplicate `backend/app/...` implementations do not appear to affect the current canonical `ExecutionGate` path, because `ExecutionGate` imports and instantiates `engine.risk.risk_governor.RiskGovernor`.

The duplicate classes remain a governance and maintenance risk because future imports could accidentally select a legacy authority.

## 6. Dashboard Authority and Duplicate Function Analysis

### Duplicate Dashboard Functions Identified

Tracked file:

```text
css_live_dashboard_v5.py
```

Duplicate function definitions:

| Function | First Definition | Later Definition | Runtime Effect If Module Executes |
| --- | --- | --- | --- |
| `execute_trade(...)` | line 351 | line 911 | Later definition shadows earlier definition. |
| `display_dashboard(...)` | line 375 | line 658 | Later definition shadows earlier definition. |

### Canonical Dashboard Target

Recent CSS phases have modified and tested:

```text
scripts/css_live_dashboard.py
```

The root-level `css_live_dashboard_v5.py` remains tracked and executable, but it is not the recent canonical dashboard integration target used by the Phase 85A through Phase 99 work.

### Dashboard Authority Determination

| File | Role | Classification |
| --- | --- | --- |
| `scripts/css_live_dashboard.py` | Current dashboard integration target and active operational script. | CANONICAL for current dashboard work |
| `css_live_dashboard_v5.py` | Older root dashboard script with duplicate definitions and direct missing import risk. | RETIREMENT_CANDIDATE |
| `scripts/css_live_dashboard_PRE_J7_BACKUP.py` | Backup dashboard copy. | LEGACY |
| `scripts/css_live_dashboard_BACKUP_BEFORE_COINBASE_BALANCE_FIX.py` | Backup dashboard copy. | LEGACY |

### Duplicate Runtime Impact

The duplicate root-level `css_live_dashboard_v5.py` definitions are real. If that module is executed, Python will bind the later function definitions, shadowing earlier implementations. This creates operator confusion and should be retired, renamed, or quarantined after Robert review.

The duplicates do not prove that the current `scripts/css_live_dashboard.py` behavior is shadowed by the root-level v5 file.

## 7. BOM and Syntax Finding Analysis

### Verification Method

The tracked Python file set was scanned with:

* `git ls-files *.py`
* AST parsing with `utf-8-sig`
* direct byte-prefix scan for UTF-8 BOM-prefixed files

### Parse Results

Tracked Python files scanned:

```text
923
```

Canonical parse failures:

```text
1
```

Verified parse failure:

```text
engine/reports/ticket_formatter.py - SyntaxError: invalid syntax, line 70
```

### BOM-Prefixed Tracked Python Files

The following tracked Python files have UTF-8 BOM prefixes but parsed successfully with `utf-8-sig`:

```text
backend/app/audit/execution_audit_ledger.py
backend/app/compliance/legal_acceptance.py
backend/app/futures/futures_contract_registry.py
backend/app/futures/futures_execution_adapter.py
backend/app/futures/futures_governor.py
backend/app/options/options_contract_registry.py
backend/app/options/options_execution_adapter.py
backend/app/options/options_governor.py
backend/app/orchestration/cross_asset_execution_orchestrator.py
backend/app/persistence/services/broker_reconciliation_service.py
backend/app/risk/capital_allocation_governor.py
backend/app/risk/portfolio_governor.py
backend/app/risk/unified_risk_execution_gate.py
backend/brokers/ibkr/ibkr_adapter.py
backend/brokers/ibkr/ibkr_runtime_manager.py
backend/intelligence/allocation_intelligence_engine.py
backend/intelligence/test_allocation_intelligence.py
backend/intelligence/test_regime_governance.py
backend/intelligence/trade_decision_orchestrator.py
```

### Canonical Versus Non-Canonical Distinction

The current tracked canonical scan verifies one syntax-invalid Python file and 19 BOM-prefixed tracked Python files. Archive copies and untracked audit artifacts were excluded from canonical authority classification.

### Current Classification

B-06 remains PARTIALLY VERIFIED:

* VERIFIED: one canonical tracked Python syntax failure exists.
* VERIFIED: 19 tracked BOM-prefixed Python files exist.
* NOT VERIFIED for current HEAD: the broader claim that all BOM-prefixed files are syntax-invalid canonical failures.

## 8. Dashboard Import Issue Analysis

### Import Evidence

Tracked references to `backend.data.coinbase_historical_downloader`:

| File | Behavior | Classification |
| --- | --- | --- |
| `scripts/css_live_dashboard.py` | Attempts import and provides `ModuleNotFoundError` fallback `load_runtime_asset(...)`. | CANONICAL dashboard safe fallback |
| `backend/scanner/unified_market_scanner.py` | Attempts import inside `try/except Exception` and falls back to `None`. | ACTIVE_SUPPORT safe fallback |
| `css_live_dashboard_v5.py` | Imports directly at module load without fallback. | RETIREMENT_CANDIDATE risk |
| `scripts/css_extended_paper_test.py` | Imports directly without fallback. | ACTIVE_SUPPORT / test-script risk |

### Missing Module Evidence

`git ls-files backend/data` returned no tracked files.

`git check-ignore -v backend\data\coinbase_historical_downloader.py` reported:

```text
.gitignore:68:data/  "backend\\data\\coinbase_historical_downloader.py"
```

This means the expected module is not tracked and is ignored by the `data/` ignore rule.

### Current Classification

B-10 remains PARTIALLY VERIFIED:

* VERIFIED: some tracked files import a non-tracked ignored module.
* VERIFIED: root-level `css_live_dashboard_v5.py` can fail at import time in a clean clone.
* VERIFIED: current `scripts/css_live_dashboard.py` has a safe fallback and should not crash on that missing module.
* VERIFIED: `backend/scanner/unified_market_scanner.py` also has a safe fallback.

## 9. Consolidated Authority Matrix

| Domain | Canonical Authority | Active Support | Legacy / Retirement Candidates | Runtime Risk |
| --- | --- | --- | --- | --- |
| Unified trade gate | `backend/governance/css_unified_trade_gate.py` | `scripts/css_live_dashboard.py` local dashboard gate | `scripts/build_r7_unified_trade_gate.py`, dashboard backups, archive copies | Medium governance ambiguity; backend path is clear. |
| Risk governor | `engine/risk/risk_governor.py` | None identified beyond direct canonical consumers | `backend/app/engine_risk.py`, `backend/app/risk_governor.py`, `backend/app/risk/risk_governor.py` | Medium future import confusion; current execution path is clear. |
| Current dashboard | `scripts/css_live_dashboard.py` | `backend/scanner/unified_market_scanner.py` enrichment fallback | `css_live_dashboard_v5.py`, backup dashboard scripts | Medium operator confusion if older script is run. |
| Dashboard import source | No tracked canonical `backend/data/coinbase_historical_downloader.py` | Fallbacks in current dashboard/scanner | Direct imports in root v5 and extended paper test | Medium clean-clone/runtime support risk. |
| Syntax/BOM hygiene | Tracked Python tree | N/A | BOM-prefixed tracked files and one syntax-invalid report file | High for tooling/import stability until remediated. |

## 10. Recommended Remediation Priority

### P2 Runtime Stability

1. Fix `engine/reports/ticket_formatter.py` syntax failure.
2. Decide whether `backend/data/coinbase_historical_downloader.py` should be tracked, replaced by a canonical adapter, or removed from direct-import consumers.
3. Remove direct missing-module imports from `css_live_dashboard_v5.py` and `scripts/css_extended_paper_test.py`, or formally retire those scripts.

### P3 Governance Consolidation

1. Declare `backend/governance/css_unified_trade_gate.py` as the only canonical backend `CSSUnifiedTradeGate`.
2. Declare `engine/risk/risk_governor.py` as the only canonical `RiskGovernor`.
3. Move backup dashboard scripts and build-time insertion scripts out of active authority surfaces or mark them explicitly as archived/non-runtime.
4. Add import linting or a governance check to prevent new duplicate authority classes.

### P4 Technical Debt

1. Normalize BOM-prefixed Python files in a mechanical cleanup phase.
2. Remove or relocate obsolete root dashboard and backup dashboard copies after Robert review.
3. Add documentation headers to retained legacy files stating that they are not canonical runtime authorities.

## 11. Validation Commands Used

Commands used during this documentation-only verification:

```text
git remote -v
git branch --show-current
git rev-parse HEAD
rg -n "class CSSUnifiedTradeGate|CSSUnifiedTradeGate" backend scripts tests --glob "*.py"
rg -n "RiskGovernor" engine backend run_sim_close.py tests --glob "*.py"
rg -n "backend\.data\.coinbase_historical_downloader|load_runtime_asset" scripts backend css_live_dashboard_v5.py --glob "*.py"
rg -n "^def display_dashboard|^def execute_trade" css_live_dashboard_v5.py scripts\css_live_dashboard.py scripts\css_live_dashboard_PRE_J7_BACKUP.py scripts\css_live_dashboard_BACKUP_BEFORE_COINBASE_BALANCE_FIX.py
git ls-files backend/data
git check-ignore -v backend\data\coinbase_historical_downloader.py
.venv\Scripts\python.exe -c "<tracked Python AST and BOM scan>"
```

No tests were run because ARP-003 is documentation-only and no runtime code was changed.

## 12. Final ARP-003 Determination

ARP-003 verifies that CSS currently has clear canonical backend authorities for the unified trade gate and risk governor, but it also confirms that tracked legacy, dashboard-local, backup, and build-script definitions remain in the repository and create governance ambiguity.

The highest-risk verified items are:

1. The canonical tracked syntax failure in `engine/reports/ticket_formatter.py`.
2. The untracked/ignored `backend.data.coinbase_historical_downloader` dependency referenced by direct-import consumers.
3. Duplicate dashboard functions in `css_live_dashboard_v5.py` if that legacy root script is executed.

Recommended next action: remediate B-06 and B-10 first for runtime stability, then perform a controlled authority consolidation phase for B-03, B-07, and B-08.
