# ARP-005 Compliance Import Remediation Report

## 1. Purpose

This report documents ARP-005 remediation for the compliance circular import involving legal acceptance persistence.

This phase was limited to compliance/legal acceptance import remediation. AntiBleedGuard, MarginTradeGate, live_toggle, live_arm, broker adapters, dashboard behavior, strategy logic, credential handling, unrelated execution logic, and unrelated risk controls were not modified.

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

HEAD before ARP-005 changes:

```text
2a21ce3c0e42c55fd372763fa3589e9ca47970bb
```

## 3. Original Issue

ARP-004 validation left one known failure:

```text
LegalAcceptanceRepository partially initialized due to a circular import in backend.app.compliance.
```

The failure blocked `tests/test_security_phase_alpha.py::test_trade_decision_orchestrator_capital_allocator_init`.

## 4. Reproduction

Command:

```text
.venv\Scripts\python.exe -m pytest tests\test_security_phase_alpha.py -q
```

Pre-fix result:

```text
1 failed, 7 passed
```

Failure:

```text
ImportError: cannot import name 'LegalAcceptanceRepository' from partially initialized module
'backend.app.persistence.repositories.legal_acceptance_repository'
```

## 5. Files Reviewed

| File | Purpose |
| --- | --- |
| `backend/app/compliance/__init__.py` | Compliance package root and export surface. |
| `backend/app/persistence/repositories/legal_acceptance_repository.py` | Durable legal acceptance repository. |
| `backend/app/compliance/legal_acceptance.py` | Legal acceptance dataclasses and validation shape helpers. |
| `backend/app/compliance/legal_acceptance_service.py` | Legal acceptance service and default repository construction path. |
| `backend/app/persistence/services/persistence_service.py` | Persistence service importing `LegalAcceptanceRepository`. |
| `backend/intelligence/trade_decision_orchestrator.py` | Import path that exposed the cycle through persistence. |
| `tests/test_security_phase_alpha.py` | Reproduction test. |
| `tests/governance/test_phase1_legal_acceptance_implementation.py` | Targeted legal acceptance governance tests. |

## 6. Root Cause

The import cycle was:

```text
backend.intelligence.trade_decision_orchestrator
  -> backend.app.persistence.services.persistence_service
  -> backend.app.persistence.repositories.legal_acceptance_repository
  -> backend.app.compliance.legal_acceptance
  -> initializes backend.app.compliance package
  -> backend.app.compliance.__init__
  -> backend.app.persistence.repositories.legal_acceptance_repository
```

The class causing partial initialization was:

```text
LegalAcceptanceRepository
```

The unsafe edge was the eager package-root re-export in:

```text
backend/app/compliance/__init__.py
```

That package root imported `LegalAcceptanceRepository` while `legal_acceptance_repository.py` was still initializing.

## 7. Remediation Approach

The safest minimal remediation was to preserve the compliance package export while making the repository import lazy.

`backend/app/compliance/__init__.py` no longer eagerly imports:

```text
backend.app.persistence.repositories.legal_acceptance_repository.LegalAcceptanceRepository
```

Instead, the package root resolves `LegalAcceptanceRepository` through `__getattr__` only when that attribute is requested.

This breaks the circular import while preserving compatibility for:

```text
from backend.app.compliance import LegalAcceptanceRepository
```

## 8. Files Changed

| File | Change |
| --- | --- |
| `backend/app/compliance/__init__.py` | Replaced eager repository re-export with lazy `__getattr__` resolution. |
| `docs/governance/ARP_005_COMPLIANCE_IMPORT_REMEDIATION_REPORT.md` | Added this remediation evidence report. |
| `certification/security/SECURITY_CERTIFICATION_EVIDENCE_REGISTER.md` | Referenced ARP-005 remediation evidence. |
| `certification/governance/GOVERNANCE_CERTIFICATION_EVIDENCE_REGISTER.md` | Referenced ARP-005 remediation evidence. |

## 9. Safety Assessment

Legal acceptance controls were not weakened:

* Legal acceptance dataclasses were not changed.
* Legal acceptance validation rules were not changed.
* Legal acceptance enforcement behavior was not changed.
* Legal acceptance repository persistence behavior was not changed.
* Fail-closed behavior was not converted to fail-open.
* No broker, execution, dashboard, risk, margin, strategy, or credential logic was changed.

## 10. Validation Results

Compile command:

```text
.venv\Scripts\python.exe -m py_compile backend\app\compliance\__init__.py
```

Result:

```text
passed
```

Required security test command:

```text
.venv\Scripts\python.exe -m pytest tests\test_security_phase_alpha.py -q
```

Result:

```text
8 passed, 1 warning
```

Legal acceptance governance test command:

```text
.venv\Scripts\python.exe -m pytest tests\governance\test_phase1_legal_acceptance_implementation.py -q
```

Result:

```text
8 passed
```

Lazy export compatibility check:

```text
.venv\Scripts\python.exe -c "from backend.app.compliance import LegalAcceptanceRepository; from backend.app.persistence.repositories.legal_acceptance_repository import LegalAcceptanceRepository as Direct; print(LegalAcceptanceRepository is Direct)"
```

Result:

```text
True
```

## 11. Remaining Risks

1. Broader compliance package import hygiene should still be reviewed during future authority consolidation.
2. The package root continues to provide a broad convenience export surface; future additions should avoid eager imports from persistence, execution, broker, or runtime layers.
3. This phase did not add new legal acceptance runtime evidence; it only restored the import path and captured validation output.

## 12. Certification Impact

ARP-005 captures remediation evidence for the compliance import cycle that blocked legal acceptance import validation.

Certification status impact:

* Evidence is CAPTURED/REFERENCED for remediation.
* No evidence is marked APPROVED.
* Robert review remains required before further certification conclusions.
