# ARP-011 Authority Quarantine Execution Report

## Purpose

ARP-011 executes the ARP-007 non-destructive authority quarantine plan by adding clear warnings and guardrails to tracked non-canonical authority surfaces. The objective is to reduce accidental use of legacy, retirement-candidate, or duplicate files without deleting, moving, renaming, or changing canonical runtime behavior.

## Pre-Check

Repository remote:

```text
origin  https://github.com/rasibor-cpu/capital-strata-systems.git (fetch)
origin  https://github.com/rasibor-cpu/capital-strata-systems.git (push)
```

Branch:

```text
css-evening-consolidation-2026-06-09
```

HEAD before ARP-011 changes:

```text
0a9630b54232175517850db3aab3c271a5fa5a6f
```

## Source Governance Reviewed

ARP-011 reviewed the following source governance documents:

* `docs/governance/ARP_006_CANONICAL_AUTHORITY_MAP.md`
* `docs/governance/ARP_006_RUNTIME_IMPORT_MAP.md`
* `docs/governance/ARP_007_NON_DESTRUCTIVE_AUTHORITY_QUARANTINE_PLAN.md`
* `docs/governance/ARP_009_AUDIT_CLOSURE_MATRIX.md`

## Files Reviewed

Tracked files reviewed for quarantine markers:

* `css_live_dashboard_v5.py`
* `scripts/build_r7_unified_trade_gate.py`
* `scripts/css_extended_paper_test.py`
* `backend/app/risk_governor.py`
* `backend/app/risk/risk_governor.py`
* `backend/app/engine_risk.py`
* `backend/risk/portfolio_risk_governor.py`
* `backend/app/security/auth_gate_PRE_PACK4.py`
* `backend/app/security/user_registry_PRE_PACK4.py`

Local untracked or non-canonical material reviewed but not modified:

* `scripts/css_live_dashboard_PRE_J7_BACKUP.py`
* `scripts/css_live_dashboard_BACKUP_BEFORE_COINBASE_BALANCE_FIX.py`
* `backend/app/pnl/test_pnl_engine.py`
* `archive/dashboard_versions/...`

These were not changed because they were not tracked in the current branch working set or were explicitly archive material outside the ARP-011 tracked-marker scope.

## Files Marked

| File | Classification | Marker Type | Canonical Replacement Reference | Runtime Impact |
| --- | --- | --- | --- | --- |
| `css_live_dashboard_v5.py` | RETIREMENT_CANDIDATE | Module docstring warning plus direct-execution guard | `scripts/css_live_dashboard.py` | Prevents accidental direct execution of the root retirement-candidate dashboard only. Import compatibility remains available. |
| `scripts/build_r7_unified_trade_gate.py` | RETIREMENT_CANDIDATE | Module docstring warning | `backend/governance/css_unified_trade_gate.py`; `scripts/css_live_dashboard.py` for dashboard-local support | No runtime behavior change. |
| `scripts/css_extended_paper_test.py` | ACTIVE_SUPPORT / RETIREMENT_CANDIDATE | Module docstring warning | `scripts/css_live_dashboard.py` | No runtime behavior change. |
| `backend/app/risk_governor.py` | LEGACY | Top-of-file governance warning | `engine/risk/risk_governor.py` | No behavior change. |
| `backend/app/risk/risk_governor.py` | LEGACY | Top-of-file governance warning | `engine/risk/risk_governor.py` | No behavior change. |
| `backend/app/engine_risk.py` | LEGACY | Module docstring warning | `engine/risk/risk_governor.py`; `engine/execution/execution_gate.py` | No behavior change. |
| `backend/risk/portfolio_risk_governor.py` | LEGACY | Module docstring warning | `engine/risk/risk_governor.py` | No behavior change. |
| `backend/app/security/auth_gate_PRE_PACK4.py` | LEGACY | Top-of-file governance warning | `backend/app/security/auth_gate.py` | No behavior change. |
| `backend/app/security/user_registry_PRE_PACK4.py` | LEGACY | Module docstring warning | `backend/app/security/user_registry.py` | No behavior change. |

## Special Dashboard Guard

`css_live_dashboard_v5.py` is classified as a retirement candidate by ARP-006 and ARP-007. ARP-011 added a direct-execution guard that exits with an operator-facing message pointing to `scripts/css_live_dashboard.py`.

This guard is intentionally limited to direct execution:

```text
python css_live_dashboard_v5.py
```

Import compatibility is preserved because the guard only runs when `__name__ == "__main__"`.

## Duplicate Gate and Risk Handling

Duplicate `CSSUnifiedTradeGate` and `RiskGovernor` surfaces were not refactored. ARP-011 added warnings only:

* The canonical backend `CSSUnifiedTradeGate` remains `backend/governance/css_unified_trade_gate.py`.
* The active dashboard-local support gate remains in `scripts/css_live_dashboard.py`.
* The canonical execution `RiskGovernor` remains `engine/risk/risk_governor.py`.

## Files Deliberately Not Changed

ARP-011 deliberately did not change:

* `backend/governance/css_unified_trade_gate.py`
* `engine/risk/risk_governor.py`
* `scripts/css_live_dashboard.py`
* `engine/execution/execution_gate.py`
* `backend/app/risk/anti_bleed_guard.py`
* `engine/risk/margin_trade_gate.py`
* broker adapters
* credential files
* archive files
* tests

## Runtime Impact Assessment

Canonical runtime behavior is unchanged.

The only intentional behavior change is a direct-execution guard on `css_live_dashboard_v5.py`, a retirement-candidate root dashboard file. This guard reduces accidental operator use of a non-canonical dashboard with duplicate dashboard functions and direct missing data imports. It does not change the active dashboard path, broker execution, risk enforcement, margin enforcement, security authorization, or trading logic.

## Validation Summary

Validation performed:

* `py_compile` for all changed Python files.
* Canonical runtime import checks for:
  * `backend.governance.css_unified_trade_gate.CSSUnifiedTradeGate`
  * `engine.risk.risk_governor.RiskGovernor`
  * `engine.execution.execution_gate.ExecutionGate`
  * `scripts.css_live_dashboard`
* Active dashboard compile check for `scripts/css_live_dashboard.py`.

## Guardrail Confirmation

ARP-011 confirms:

* No files were deleted.
* No files were moved.
* No files were renamed.
* No imports were changed.
* No canonical logic was changed.
* No broker adapters were changed.
* No credential files were changed.
* No trading logic was changed.
* No dashboard behavior was changed except the direct-execution guard on the retirement-candidate root dashboard.

## Certification Impact

ARP-011 provides governance and operations evidence that duplicate authority surfaces have been explicitly marked as non-canonical while preserving canonical runtime behavior. Relevant certification evidence registers should reference this report as CAPTURED or REFERENCED evidence, not APPROVED evidence.

## Remaining Risks

* Untracked local backup files remain present in the working tree and may continue to confuse local-only audits.
* Archive dashboard versions were not modified in this phase.
* A future approved phase may add import-regression tests or move retirement candidates to a formal archive/quarantine location after Robert review.
* Destructive cleanup remains out of scope.
