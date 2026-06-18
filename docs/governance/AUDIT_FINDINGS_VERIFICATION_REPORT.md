# Audit Findings Verification Report

## ARP-001 Scope

This report verifies material findings from the CSS Institutional Audit dated 2026-06-13 against branch `css-evening-consolidation-2026-06-09` at starting commit `4e469ec53bc2aed20e94c5b35de97e716c17bd07`.

This phase is verification and remediation planning only. No runtime, execution, broker, dashboard, risk, margin, security, authentication, authorization, credential, or trading logic changes are made by this report.

## Verification Summary

| Finding | Audit Severity | Classification | Summary |
| --- | --- | --- | --- |
| B-01 | Critical | VERIFIED | AntiBleedGuard exists but is not imported or called outside its definition file. |
| B-02 | Critical | VERIFIED | `live_toggle.py` hardcodes `ctx.user_id != "1369"` instead of RBAC/role authorization. |
| B-03 | Critical | PARTIALLY VERIFIED | Duplicate functions exist in tracked root `css_live_dashboard_v5.py`; current canonical dashboard work targets `scripts/css_live_dashboard.py`. |
| B-04 | Critical | VERIFIED | MarginTradeGate is display-visible but not enforced in canonical trade gate or trade decision path. |
| B-05 | Critical | NOT VERIFIED | Claimed compliance circular import did not reproduce on current HEAD. |
| B-06 | High | PARTIALLY VERIFIED | Current canonical AST scan finds 1 syntax failure, not 20; BOM files exist but parse with `utf-8-sig`. |
| B-07 | High | PARTIALLY VERIFIED | Multiple CSSUnifiedTradeGate definitions exist; backend canonical path is identifiable, with dashboard/build duplicates. |
| B-08 | High | PARTIALLY VERIFIED | Four RiskGovernor definitions exist; engine path appears canonical for execution/tests, but authority is not formally consolidated. |
| B-09 | High | VERIFIED | `live_arm.py` exists but is not imported or called by the current live execution gate. |
| B-10 | High | PARTIALLY VERIFIED | Dashboard import target exists locally but is ignored/untracked, so a clean clone of HEAD lacks it. |

## B-01 - AntiBleedGuard Disconnected From Execution Path

**Audit Claim:** AntiBleedGuard is defined but has zero imports anywhere in the codebase and is disconnected from execution paths.

**Verification Method:**

* `rg -n "AntiBleedGuard|anti_bleed|AntiBleed" backend engine scripts dashboard css_live_dashboard_v5.py --glob "*.py"`
* Read `backend/app/risk/anti_bleed_guard.py`.
* Checked trade decision path references in `backend/intelligence/trade_decision_orchestrator.py`.

**Verification Result:** VERIFIED

**Evidence:**

* `backend/app/risk/anti_bleed_guard.py:12` defines `class AntiBleedGuard`.
* No canonical import or call site was found outside `backend/app/risk/anti_bleed_guard.py`.
* `TradeDecisionOrchestrator.evaluate_trade()` delegates to `_build_decision_payload()` and does not invoke AntiBleedGuard.

**Affected Files:**

* `backend/app/risk/anti_bleed_guard.py`
* `backend/intelligence/trade_decision_orchestrator.py`
* Potential intended integration: canonical trade permission path or trade decision orchestration path.

**Risk Assessment:**

Cost/bleed protection exists as isolated code but cannot block or warn in the current execution or decision path. If production execution were enabled elsewhere, this control would provide no protection.

**Recommended Remediation:**

* Define the canonical insertion point before implementation. Likely candidates are the CSS Unified Trade Gate decision envelope or trade decision orchestration before any executable approval.
* Add tests proving low-edge, fee-heavy, rapid-repeat, and undersized trades are blocked or flagged.
* Ensure any integration does not bypass existing CSS Unified Trade Gate, broker, capital, risk, or margin controls.

## B-02 - `live_toggle.py` Uses Hardcoded User ID

**Audit Claim:** `backend/app/security/live_toggle.py` hardcodes `user_id='1369'`, bypassing RBAC.

**Verification Method:**

* Read `backend/app/security/live_toggle.py`.
* Read `engine/run_engine.py`.
* Searched for `require_live_allowed`.

**Verification Result:** VERIFIED

**Evidence:**

* `backend/app/security/live_toggle.py` checks `if ctx.user_id != "1369":`.
* `engine/run_engine.py` imports and calls `require_live_allowed()` before `run_engine_loop()`.
* `require_live_allowed()` checks engine mode and user ID, but does not verify RBAC role, SUPER_USER authorization, two-key live arming, or formal approval state.

**Affected Files:**

* `backend/app/security/live_toggle.py`
* `engine/run_engine.py`
* Related but disconnected: `backend/app/ops/live_arm.py`

**Risk Assessment:**

Live-mode authorization is coupled to a single hardcoded identity rather than role/permission policy. A context with user ID `1369` is allowed regardless of role, while authorized roles with other IDs are blocked. This is a security and operations risk.

**Recommended Remediation:**

* Replace hardcoded user ID logic with RBAC/SUPER_USER policy.
* Require live arming and explicit approval in the same live boundary.
* Add audit events for allowed and denied live authorization decisions.
* Add tests for authorized role allowed, unauthorized role denied, missing context denied, and live arm absent denied.

## B-03 - Duplicate Dashboard Function Definitions

**Audit Claim:** `css_live_dashboard_v5.py` has duplicate definitions of `display_dashboard` and `execute_trade`.

**Verification Method:**

* `Select-String -Path css_live_dashboard_v5.py -Pattern '^def display_dashboard|^def execute_trade'`
* Checked references to `css_live_dashboard_v5.py`.
* Checked `scripts/css_live_dashboard.py` for the same function names.

**Verification Result:** PARTIALLY VERIFIED

**Evidence:**

* `css_live_dashboard_v5.py:351` defines `execute_trade(candidate, broker, position_managers)`.
* `css_live_dashboard_v5.py:911` defines `execute_trade(candidate, broker, position_managers, state)`.
* `css_live_dashboard_v5.py:375` defines `display_dashboard(state, broker_name, engine_mode, cycle, pnl_snapshot)`.
* `css_live_dashboard_v5.py:658` defines `display_dashboard(state, broker_name, engine_mode, cycle, pnl_snapshot, metrics)`.
* `scripts/css_live_dashboard.py` is the current file modified in recent dashboard phases; it does not define those duplicate root-v5 functions.
* No canonical references to `css_live_dashboard_v5.py` were found in the targeted search.

**Affected Files:**

* `css_live_dashboard_v5.py`
* Current dashboard target: `scripts/css_live_dashboard.py`

**Risk Assessment:**

The duplicate definitions are real in a tracked root dashboard file. Python deterministically binds the later definition, so the behavior is shadowed rather than random. Runtime impact is only verified if `css_live_dashboard_v5.py` is executed or imported; current phase work has treated `scripts/css_live_dashboard.py` as canonical.

**Recommended Remediation:**

* Decide whether `css_live_dashboard_v5.py` is legacy or canonical.
* If legacy, archive/remove it from runnable surfaces or document it as non-canonical.
* If retained, consolidate duplicate functions and add import/compile coverage.

## B-04 - MarginTradeGate Not Enforced in Canonical Trade Path

**Audit Claim:** MarginTradeGate is documented but not wired to CSSUnifiedTradeGate, broker execution, or capital governor, so margin cannot block trades.

**Verification Method:**

* `rg -n "class MarginTradeGate|MarginTradeGate|CSSUnifiedTradeGate" backend engine scripts dashboard css_live_dashboard_v5.py --glob "*.py"`
* Read `engine/risk/margin_trade_gate.py`.
* Read `scripts/css_live_dashboard.py` margin dashboard helper.
* Read `backend/governance/css_unified_trade_gate.py`.
* Read `backend/intelligence/trade_decision_orchestrator.py`.

**Verification Result:** VERIFIED

**Evidence:**

* `engine/risk/margin_trade_gate.py` defines `MarginTradeGate`.
* `scripts/css_live_dashboard.py:435` imports `MarginTradeGate` inside `margin_dashboard_lines()`.
* `scripts/css_live_dashboard.py:458` evaluates `MarginTradeGate()` for dashboard display.
* `backend/governance/css_unified_trade_gate.py` contains no `MarginTradeGate` import/use.
* `backend/intelligence/trade_decision_orchestrator.py` imports `CSSUnifiedTradeGate` but does not call margin gate logic.
* Phase 100C/101A governance docs also identify margin enforcement as deferred.

**Affected Files:**

* `engine/risk/margin_trade_gate.py`
* `scripts/css_live_dashboard.py`
* `backend/governance/css_unified_trade_gate.py`
* `backend/intelligence/trade_decision_orchestrator.py`

**Risk Assessment:**

Margin state is visible and decisionable, but not authoritative for blocking new exposure in the canonical trade path. This is a production blocker for margin-aware live trading.

**Recommended Remediation:**

* Define an approved integration path for MarginTradeGate into CSSUnifiedTradeGate or a unified risk decision envelope.
* Ensure LIVE UNKNOWN margin state fails closed before new exposure.
* Add tests proving GREEN/YELLOW allow, ORANGE/RED/BLACK/UNKNOWN block as required.

## B-05 - Circular Import in Compliance Module

**Audit Claim:** `backend.app.compliance.__init__` imports `LegalAcceptanceRepository`, which imports `LegalAcceptanceRecord` from compliance, causing a circular import failure.

**Verification Method:**

* Read `backend/app/compliance/__init__.py`.
* Read `backend/app/persistence/repositories/legal_acceptance_repository.py`.
* Executed read-only imports with venv Python:
  * `import backend.app.compliance`
  * `import backend.app.persistence.repositories.legal_acceptance_repository`
  * `import backend.intelligence.trade_decision_orchestrator`

**Verification Result:** NOT VERIFIED

**Evidence:**

* Static import dependency exists: `compliance.__init__` imports `LegalAcceptanceRepository`; repository imports `backend.app.compliance.legal_acceptance`.
* Current HEAD import test succeeded for all three modules listed above.
* No ImportError reproduced during verification.

**Affected Files:**

* `backend/app/compliance/__init__.py`
* `backend/app/persistence/repositories/legal_acceptance_repository.py`
* `backend/app/compliance/legal_acceptance.py`

**Risk Assessment:**

There is coupling between compliance package exports and persistence repository imports. However, the specific circular ImportError claim did not reproduce at current HEAD. Treat as a design smell, not a verified production blocker.

**Recommended Remediation:**

* Do not prioritize as P0 unless a failing import path is reproduced.
* Consider later cleanup by removing persistence repository exports from `compliance.__init__` if package boundaries should be stricter.

## B-06 - Syntax-Invalid/BOM-Corrupted Files

**Audit Claim:** 20 canonical Python files have syntax errors or BOM corruption.

**Verification Method:**

* AST scan using venv Python with `ast.parse` and `utf-8-sig` decode.
* Canonical scan excluded `.venv`, `.pytest_cache`, `CLAUDE_FULL_SYSTEM_AUDIT`, `archive`, and `REPO_AUDIT_ARTIFACTS`.
* Full scan included audit-copy trees to distinguish canonical and non-canonical failures.
* Byte scan for UTF-8 BOM-prefixed `.py` files.

**Verification Result:** PARTIALLY VERIFIED

**Evidence:**

Canonical AST scan:

* Scanned: 923 Python files.
* Failures: 1.
* Failing canonical file:
  * `engine/reports/ticket_formatter.py` - `SyntaxError: invalid syntax (ticket_formatter.py, line 70)`.

Full AST scan including audit-copy trees:

* Scanned: 2154 Python files.
* Failures: 2.
* Failures:
  * `engine/reports/ticket_formatter.py` - `SyntaxError: invalid syntax (ticket_formatter.py, line 70)`.
  * `CLAUDE_FULL_SYSTEM_AUDIT/engine/reports/ticket_formatter.py` - same copied failure.

Canonical UTF-8 BOM-prefixed Python files that parsed successfully with `utf-8-sig`:

* `scripts/test_cross_asset_orchestrator.py`
* `backend/intelligence/trade_decision_orchestrator.py`
* `backend/intelligence/test_regime_governance.py`
* `backend/intelligence/test_allocation_intelligence.py`
* `backend/intelligence/allocation_intelligence_engine.py`
* `backend/brokers/ibkr/ibkr_runtime_manager.py`
* `backend/brokers/ibkr/ibkr_adapter.py`
* `backend/app/risk/unified_risk_execution_gate.py`
* `backend/app/risk/portfolio_governor.py`
* `backend/app/risk/capital_allocation_governor.py`
* `backend/app/persistence/services/broker_reconciliation_service.py`
* `backend/app/orchestration/cross_asset_execution_orchestrator.py`
* `backend/app/options/options_governor.py`
* `backend/app/options/options_execution_adapter.py`
* `backend/app/options/options_contract_registry.py`
* `backend/app/futures/futures_governor.py`
* `backend/app/futures/futures_execution_adapter.py`
* `backend/app/futures/futures_contract_registry.py`
* `backend/app/compliance/legal_acceptance.py`

**Affected Files:**

* Canonical parse failure: `engine/reports/ticket_formatter.py`.
* BOM-prefixed but parseable canonical files listed above.

**Risk Assessment:**

The audit count of 20 canonical syntax failures is stale for current HEAD. There is one verified canonical syntax failure. BOM prefixes are present in 19 canonical files but did not cause AST parse failure under `utf-8-sig`; they still merit normalization because tooling may vary.

**Recommended Remediation:**

* Fix `engine/reports/ticket_formatter.py` first because it cannot parse.
* Normalize BOM-prefixed canonical Python files in a separate mechanical cleanup with compile validation.
* Exclude `CLAUDE_FULL_SYSTEM_AUDIT` from remediation scope unless explicitly approved.

## B-07 - Multiple CSSUnifiedTradeGate Definitions

**Audit Claim:** CSSUnifiedTradeGate has multiple definitions and governance authority is not singular.

**Verification Method:**

* `rg -n "class CSSUnifiedTradeGate|CSSUnifiedTradeGate" backend engine scripts dashboard css_live_dashboard_v5.py --glob "*.py"`
* Read import usage in backend components.

**Verification Result:** PARTIALLY VERIFIED

**Evidence:**

Canonical/backend definition:

* `backend/governance/css_unified_trade_gate.py:41`
* Imported by `backend/intelligence/trade_decision_orchestrator.py`.
* Imported by `backend/app/brokers/live_readiness_certifier.py`.
* Imported by `tests/test_security_phase_alpha.py`.

Runtime/dashboard local definition:

* `scripts/css_live_dashboard.py:1926`
* Instantiated as `css_unified_trade_gate` in that dashboard script.

Script/build implementation:

* `scripts/build_r7_unified_trade_gate.py:9`

Legacy/backup implementations:

* `scripts/css_live_dashboard_PRE_J7_BACKUP.py`
* `scripts/css_live_dashboard_BACKUP_BEFORE_COINBASE_BALANCE_FIX.py`

**Affected Files:**

* `backend/governance/css_unified_trade_gate.py`
* `scripts/css_live_dashboard.py`
* `scripts/build_r7_unified_trade_gate.py`
* legacy backup scripts listed above

**Risk Assessment:**

Multiple definitions are real. Backend imports identify a likely canonical implementation, but the dashboard carries its own local class. This can create governance drift, especially if dashboard and backend gates diverge. The build script is non-runtime generation code; backup files are legacy.

**Recommended Remediation:**

* Declare `backend/governance/css_unified_trade_gate.py` as canonical or choose another explicit authority.
* Remove or rename local dashboard gate definitions after safe migration.
* Ensure dashboard consumes canonical gate output rather than defining gate authority.

## B-08 - Multiple RiskGovernor Definitions

**Audit Claim:** Four distinct RiskGovernor classes exist with no declared canonical authority.

**Verification Method:**

* `rg -n "class RiskGovernor" backend engine scripts dashboard css_live_dashboard_v5.py --glob "*.py"`
* Searched import usage for `RiskGovernor`.
* Read backend/app variants.

**Verification Result:** PARTIALLY VERIFIED

**Evidence:**

Definitions found:

* `engine/risk/risk_governor.py:70`
* `backend/app/engine_risk.py:46`
* `backend/app/risk_governor.py:14`
* `backend/app/risk/risk_governor.py:16`

Import/use evidence:

* `engine/execution/execution_gate.py` imports `engine.risk.risk_governor.RiskGovernor`.
* `backend/app/run_live_guarded.py` imports `engine.risk.risk_governor.RiskGovernor`.
* `tests/engine/test_risk_governor.py` imports `engine.risk.risk_governor.RiskGovernor`.

**Affected Files:**

* `engine/risk/risk_governor.py`
* `backend/app/engine_risk.py`
* `backend/app/risk_governor.py`
* `backend/app/risk/risk_governor.py`
* `engine/execution/execution_gate.py`
* `backend/app/run_live_guarded.py`

**Risk Assessment:**

Multiple definitions are real. Current execution/test references indicate `engine/risk/risk_governor.py` is the practical canonical path, but the repository does not clearly deprecate the others. Risk behavior can differ if code imports alternate governors.

**Recommended Remediation:**

* Declare canonical risk governor authority.
* Deprecate or wrap alternate definitions.
* Add import-boundary tests ensuring execution paths use the canonical governor.

## B-09 - `live_arm` Disconnected From Execution Path

**Audit Claim:** `live_arm.py` two-key arming exists but is not imported or called from runtime.

**Verification Method:**

* `rg -n "live_arm|live_armed|assert_live_armed_or_block|REA_LIVE_ARM|REA_CONFIRM_LIVE" backend engine scripts dashboard css_live_dashboard_v5.py --glob "*.py"`
* Read `backend/app/ops/live_arm.py`.
* Read `backend/app/security/live_toggle.py`.
* Read `engine/run_engine.py`.

**Verification Result:** VERIFIED

**Evidence:**

* `backend/app/ops/live_arm.py` defines `live_armed()` and `assert_live_armed_or_block()`.
* No non-definition import/call of `assert_live_armed_or_block()` was found.
* `engine/run_engine.py` calls `require_live_allowed()`.
* `backend/app/security/live_toggle.py` does not call `live_arm`.

**Affected Files:**

* `backend/app/ops/live_arm.py`
* `backend/app/security/live_toggle.py`
* `engine/run_engine.py`

**Risk Assessment:**

Two-key live arming exists but cannot block live execution because it is not wired into the live execution boundary. Combined with B-02, live safety depends on hardcoded identity rather than layered authorization.

**Recommended Remediation:**

* Integrate `assert_live_armed_or_block()` into the same canonical live boundary as RBAC authorization.
* Require both RBAC/SUPER_USER authorization and two-key arming for LIVE mode.
* Add tests for all combinations of mode, RBAC, and live-arm environment.

## B-10 - Dashboard Imports Non-Existent Module

**Audit Claim:** `css_live_dashboard_v5.py` imports `backend.data.coinbase_historical_downloader`, which does not exist in the repository.

**Verification Method:**

* `Select-String -Path css_live_dashboard_v5.py -Pattern "coinbase_historical_downloader|backend.data"`
* `Get-ChildItem -Recurse -Filter coinbase_historical_downloader.py`
* `git ls-tree -r HEAD --name-only backend/data`
* `git check-ignore -v backend/data/coinbase_historical_downloader.py`
* `git status --ignored --short backend/data/coinbase_historical_downloader.py`

**Verification Result:** PARTIALLY VERIFIED

**Evidence:**

* `css_live_dashboard_v5.py:11` imports `from backend.data.coinbase_historical_downloader import load_runtime_asset`.
* A local working-tree file exists at `backend/data/coinbase_historical_downloader.py`.
* The file is ignored by `.gitignore` via `data/`, and `backend/data/` is not tracked in `HEAD`.
* `git ls-tree -r HEAD --name-only backend/data` returned no tracked files.
* `git status --ignored --short backend/data/coinbase_historical_downloader.py` reports `!! backend/data/`.

**Affected Files:**

* `css_live_dashboard_v5.py`
* ignored/untracked local path: `backend/data/coinbase_historical_downloader.py`
* `.gitignore`

**Risk Assessment:**

The module is present locally but absent from the tracked repository. A clean clone of the audited commit would not contain the import target, so the dashboard import is a reproducibility/runtime risk if `css_live_dashboard_v5.py` is executed.

**Recommended Remediation:**

* Decide whether `backend/data/coinbase_historical_downloader.py` is legitimate source code or generated/local data.
* If legitimate, move it to a tracked source path or adjust `.gitignore` intentionally.
* If not canonical, remove or replace the import from `css_live_dashboard_v5.py`.

## Overall Remediation Priorities

1. P0 Critical Safety: B-04, B-01, B-09.
2. P1 Security: B-02.
3. P2 Runtime Stability: B-06, B-10, B-03.
4. P3 Governance Consolidation: B-07, B-08.
5. Verification Watchlist: B-05.

## ARP-001 Completion Notes

No remediation code was implemented in this phase. This report is intended to guide subsequent remediation phases after Robert review.
