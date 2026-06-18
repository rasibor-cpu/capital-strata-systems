# ARP-008 Controlled Evidence Capture Report

## 1. Purpose

ARP-008 captures controlled evidence proving that the remediated branch is parse-clean, import/compile-clean for targeted safety files, and test-clean for remediated safety, security, governance, and margin controls.

This phase is evidence capture only. No new functionality was added and no runtime behavior was changed.

## 2. Evidence Folder Location

```text
certification/testing/ARP_008_CONTROLLED_EVIDENCE/
```

## 3. Evidence Files Created

| File | Evidence Captured |
| --- | --- |
| `01_git_precheck.txt` | Remote, branch, and starting HEAD. |
| `02_ast_bom_scan.txt` | Tracked non-archive Python AST/BOM verification. |
| `03_py_compile_changed_safety_files.txt` | Compile evidence for remediated safety/control files and related tests. |
| `04_antibleed_tests.txt` | AntiBleedGuard integration tests. |
| `05_live_toggle_live_arm_tests.txt` | live_toggle/live_arm RBAC and authorization tests. |
| `06_margin_trade_gate_tests.txt` | MarginTradeGate unit and enforcement integration tests. |
| `07_security_tests.txt` | Security phase alpha tests. |
| `08_governance_legal_acceptance_tests.txt` | Governance/legal acceptance implementation tests. |
| `09_targeted_safety_suite_summary.txt` | RiskGovernor tests and aggregate targeted safety result summary. |
| `10_git_status_after_validation.txt` | Git status after evidence validation. |
| `ARP_008_EVIDENCE_SUMMARY.md` | Human-readable evidence package summary. |

## 4. Validation Summary

Branch:

```text
css-evening-consolidation-2026-06-09
```

Starting HEAD:

```text
80315f5e7ae3ebf1661125167e2fa8a353fb56c6
```

Validation results:

| Validation | Result |
| --- | --- |
| Git precheck | PASS |
| Tracked non-archive AST/BOM scan | PASS: `FAILURES 0`, `BOM 0` |
| Safety/control file compile | PASS: 14 files compiled |
| AntiBleedGuard tests | PASS: 5 passed, 1 warning |
| live_toggle/live_arm tests | PASS: 12 passed |
| MarginTradeGate tests | PASS: 15 passed, 6 warnings |
| Security tests | PASS: 8 passed |
| Governance/legal acceptance tests | PASS: 8 passed |
| RiskGovernor tests | PASS: 8 passed, 1 warning |

No targeted test failures were captured.

## 5. Certification Registers Updated

The following certification registers were updated because ARP-008 evidence was actually captured:

| Register | Update |
| --- | --- |
| `certification/risk/RISK_CERTIFICATION_EVIDENCE_REGISTER.md` | Added ARP-008 controlled safety evidence reference. |
| `certification/margin/MARGIN_CERTIFICATION_EVIDENCE_REGISTER.md` | Added ARP-008 controlled margin evidence reference. |
| `certification/security/SECURITY_CERTIFICATION_EVIDENCE_REGISTER.md` | Added ARP-008 controlled security/live authorization evidence reference. |
| `certification/governance/GOVERNANCE_CERTIFICATION_EVIDENCE_REGISTER.md` | Added ARP-008 controlled legal acceptance evidence reference. |
| `certification/testing/README.md` | Updated testing evidence status to captured. |
| `docs/governance/PHASE100B_CERTIFICATION_EVIDENCE_REGISTRY.md` | Added ARP-008 controlled remediation evidence package to the test evidence register. |

Only `CAPTURED` or `REFERENCED` evidence status was used. No evidence was marked `APPROVED`.

## 6. Remaining Risks

Known warnings remain:

* `backend/app/risk/anti_bleed_guard.py` emits a `datetime.utcnow()` deprecation warning under Python's current warning behavior.
* Usage-string invalid escape warnings remain in `run_replay_from_csv.py` and `tools/generate_regime_replay_csv.py`; these are not parse failures.
* `.pytest_cache/` permission warning appears during final git status capture.

Known evidence limitations:

* ARP-008 is targeted evidence, not a full repository-wide test suite.
* ARP-008 does not perform live broker validation.
* ARP-008 does not certify production readiness.
* Robert review remains required.

## 7. Recommended Next Phase

Recommended ARP-009 direction:

* Capture controlled runtime startup/shutdown evidence without live order placement.
* Preserve broker, dashboard, and credential boundaries.
* Continue evidence capture before any destructive cleanup or production certification step.

## 8. Documentation-Only / Evidence-Only Confirmation

ARP-008 confirms:

* No runtime behavior changes were made.
* No execution logic changes were made.
* No broker adapter changes were made.
* No dashboard changes were made.
* No credential changes were made.
* No new functionality was added.
