# ARP-004 Syntax and BOM Remediation Report

## 1. Purpose

This report documents ARP-004 remediation for audit finding B-06: syntax and BOM issues in canonical Python files.

This phase was limited to syntax/BOM remediation only. No execution logic, broker logic, dashboard behavior, risk rules, margin rules, security authorization, strategy logic, or credential handling was changed.

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

HEAD before ARP-004 changes:

```text
e173289247598f7ffbd4312b13f27d66189dc40a
```

## 3. Original Audit Finding

B-06 reported syntax-invalid and/or BOM-corrupted Python files.

ARP-003 verified the current active tracked Python tree contained:

* 1 syntax-invalid tracked Python file.
* 19 tracked Python files with UTF-8 BOM prefixes.
* No verified archive-only remediation requirement for this phase.

## 4. Verification Method

The repository was scanned with:

* `git ls-files "*.py"` to restrict the scan to tracked Python files.
* Exclusions for clearly non-canonical audit/archive paths:
  * `archive/`
  * `CLAUDE_FULL_SYSTEM_AUDIT/`
  * `REPO_AUDIT_ARTIFACTS/`
* AST parsing with `utf-8-sig`.
* Direct byte-prefix detection for UTF-8 BOM bytes.

Initial scan result:

```text
SCANNED 923
FAILURES 1
FAIL|engine/reports/ticket_formatter.py|SyntaxError|invalid syntax|70
BOM 19
```

## 5. Failing Files Found and Classification

### Syntax Failure

| File | Issue | Classification | Remediated |
| --- | --- | --- | --- |
| `engine/reports/ticket_formatter.py` | Mechanical token concatenation at line 70: `return "\n".join(lines)from ...` | ACTIVE_SUPPORT | Yes |

### BOM-Prefixed Files

| File | Issue | Classification | Remediated |
| --- | --- | --- | --- |
| `backend/app/audit/execution_audit_ledger.py` | UTF-8 BOM prefix | CANONICAL_ACTIVE | Yes |
| `backend/app/compliance/legal_acceptance.py` | UTF-8 BOM prefix | CANONICAL_ACTIVE | Yes |
| `backend/app/futures/futures_contract_registry.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/app/futures/futures_execution_adapter.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/app/futures/futures_governor.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/app/options/options_contract_registry.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/app/options/options_execution_adapter.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/app/options/options_governor.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/app/orchestration/cross_asset_execution_orchestrator.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/app/persistence/services/broker_reconciliation_service.py` | UTF-8 BOM prefix | CANONICAL_ACTIVE | Yes |
| `backend/app/risk/capital_allocation_governor.py` | UTF-8 BOM prefix | CANONICAL_ACTIVE | Yes |
| `backend/app/risk/portfolio_governor.py` | UTF-8 BOM prefix | CANONICAL_ACTIVE | Yes |
| `backend/app/risk/unified_risk_execution_gate.py` | UTF-8 BOM prefix | CANONICAL_ACTIVE | Yes |
| `backend/brokers/ibkr/ibkr_adapter.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/brokers/ibkr/ibkr_runtime_manager.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/intelligence/allocation_intelligence_engine.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/intelligence/test_allocation_intelligence.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/intelligence/test_regime_governance.py` | UTF-8 BOM prefix | ACTIVE_SUPPORT | Yes |
| `backend/intelligence/trade_decision_orchestrator.py` | UTF-8 BOM prefix | CANONICAL_ACTIVE | Yes |

## 6. Remediation Performed

### BOM-Only Files

The UTF-8 BOM byte sequence was removed from the 19 tracked active/support files listed above. File contents after the BOM were preserved byte-for-byte.

### Syntax-Invalid File

`engine/reports/ticket_formatter.py` was corrected by separating a mechanically concatenated `return` statement and import statement:

```text
return "\n".join(lines)from engine.domain.executions import ExecutionReport
```

became:

```text
return "\n".join(lines)


from engine.domain.executions import ExecutionReport
```

This was the minimal correction required for Python parsing. No formatter behavior or execution behavior was intentionally changed.

## 7. Files Deliberately Not Remediated

No archive-only syntax or BOM failures were remediated in this phase.

Two syntax warnings were observed during AST scanning but were not parse failures and were not remediated under ARP-004:

```text
run_replay_from_csv.py: invalid escape sequence warning in usage text
tools/generate_regime_replay_csv.py: invalid escape sequence warning in usage text
```

These warnings should be handled separately if Robert wants a warning-clean hygiene phase.

## 8. Validation Results

### Py Compile for Changed Python Files

Command:

```text
.venv\Scripts\python.exe - <py_compile script for all changed Python files>
```

Result:

```text
20 changed Python files compiled successfully.
```

### Post-Remediation AST/BOM Scan

Command:

```text
.venv\Scripts\python.exe - <tracked Python AST/BOM scan>
```

Result:

```text
SCANNED 923
FAILURES 0
BOM 0
```

### Targeted Tests

Command:

```text
.venv\Scripts\python.exe -m pytest tests\test_security_phase_alpha.py backend\intelligence\test_allocation_intelligence.py backend\intelligence\test_regime_governance.py -q
```

Result:

```text
7 passed, 1 failed
```

Failure:

```text
tests/test_security_phase_alpha.py::test_trade_decision_orchestrator_capital_allocator_init
ImportError: cannot import name 'LegalAcceptanceRepository' from partially initialized module
```

Assessment:

This failure is the existing compliance circular-import issue previously identified by the audit program. It is not caused by BOM removal or the ticket formatter syntax correction.

Follow-up command:

```text
.venv\Scripts\python.exe -m pytest tests\test_security_phase_alpha.py -q -k "not trade_decision_orchestrator_capital_allocator_init"
```

Result:

```text
7 passed, 1 deselected
```

Command:

```text
.venv\Scripts\python.exe -m pytest backend\intelligence\test_allocation_intelligence.py backend\intelligence\test_regime_governance.py -q
```

Result:

```text
no tests ran
```

Assessment:

Those two touched backend intelligence files compile successfully, but pytest did not collect tests from them.

## 9. Remaining Risks

1. The compliance circular import remains unresolved and should be handled under the relevant audit remediation phase.
2. `engine/reports/ticket_formatter.py` still contains duplicate formatter definitions after the minimal syntax correction. This was intentionally not consolidated in ARP-004 because the phase was limited to syntax/BOM remediation.
3. Syntax warnings in usage strings remain in `run_replay_from_csv.py` and `tools/generate_regime_replay_csv.py`; they do not currently block AST parsing.
4. This phase did not attempt to remediate archive, backup, or non-canonical artifacts.

## 10. Certification Impact

ARP-004 converts B-06 from a verified active syntax/BOM hygiene issue into a remediated state for tracked non-archive Python files:

* Active tracked Python AST parse failures: 0.
* Active tracked Python BOM-prefixed files: 0.
* Changed Python files compile: yes.

No certification evidence was marked APPROVED by this phase.
