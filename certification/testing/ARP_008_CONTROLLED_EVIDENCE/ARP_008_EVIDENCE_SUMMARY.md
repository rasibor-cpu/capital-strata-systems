# ARP-008 Controlled Evidence Summary

## Branch

```text
css-evening-consolidation-2026-06-09
```

## Starting HEAD

```text
80315f5e7ae3ebf1661125167e2fa8a353fb56c6
```

## Commands Executed

| Evidence File | Command / Activity | Result |
| --- | --- | --- |
| `01_git_precheck.txt` | `git remote -v`; `git branch --show-current`; `git rev-parse HEAD` | PASS |
| `02_ast_bom_scan.txt` | Tracked non-archive Python AST/BOM scan | PASS: `FAILURES 0`, `BOM 0` |
| `03_py_compile_changed_safety_files.txt` | `py_compile` for remediated safety/control files and directly related tests | PASS: 14 files compiled |
| `04_antibleed_tests.txt` | `.venv\Scripts\python.exe -m pytest tests\test_antibleed_guard_integration.py -q` | PASS: 5 passed, 1 warning |
| `05_live_toggle_live_arm_tests.txt` | `.venv\Scripts\python.exe -m pytest tests\test_live_toggle_rbac.py -q` | PASS: 12 passed |
| `06_margin_trade_gate_tests.txt` | `.venv\Scripts\python.exe -m pytest tests\test_margin_trade_gate.py tests\test_margin_trade_gate_enforcement_integration.py -q` | PASS: 15 passed, 6 warnings |
| `07_security_tests.txt` | `.venv\Scripts\python.exe -m pytest tests\test_security_phase_alpha.py -q` | PASS: 8 passed |
| `08_governance_legal_acceptance_tests.txt` | `.venv\Scripts\python.exe -m pytest tests\governance\test_phase1_legal_acceptance_implementation.py -q` | PASS: 8 passed |
| `09_targeted_safety_suite_summary.txt` | `.venv\Scripts\python.exe -m pytest tests\engine\test_risk_governor.py -q`; captured safety suite summary | PASS: 8 passed, 1 warning |
| `10_git_status_after_validation.txt` | `git status --short` after validation | CAPTURED |

## Known Warnings

The following non-failing warnings were captured:

* `backend/app/risk/anti_bleed_guard.py` uses `datetime.utcnow()`, producing a Python deprecation warning in AntiBleedGuard, MarginTradeGate enforcement, and RiskGovernor tests.
* The AST scan captures usage-string `SyntaxWarning` messages in `run_replay_from_csv.py` and `tools/generate_regime_replay_csv.py`; these are warnings, not parse failures.
* `git status --short` reported `.pytest_cache/` permission warning while capturing final status evidence.

## Remaining Failures

No test failures were captured in the ARP-008 targeted evidence package.

## Certification Impact

ARP-008 captures controlled evidence that the remediated branch is:

* parse-clean for tracked non-archive Python files;
* BOM-clean for tracked non-archive Python files;
* compile-clean for remediated safety/control files and directly related tests;
* test-clean for targeted AntiBleedGuard, live_toggle/live_arm, MarginTradeGate, security, governance/legal acceptance, and RiskGovernor suites.

This package is evidence capture only. It does not approve certification. Robert review remains required.
