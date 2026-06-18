# Item 5 Compliance Circular Import Remediation

## Scope

Item 5 addresses the known compliance circular import concern involving legal acceptance repository access through the compliance package.

This remediation is structural verification and regression coverage only. No compliance rules, trading behavior, broker behavior, risk behavior, margin behavior, dashboard behavior, authentication behavior, or credential handling were changed.

## Issue Identified

The historical failure mode was a circular import or partially initialized module error involving:

```text
backend.app.compliance
backend.app.compliance.legal_acceptance_service
backend.app.persistence.repositories.legal_acceptance_repository
```

The risky import shape is:

```text
from backend.app.compliance import LegalAcceptanceRepository
```

because `LegalAcceptanceRepository` lives under persistence while it imports compliance legal acceptance models.

## Reproduction Command

The prior circular import reproduction command is represented by:

```text
.\.venv\Scripts\python.exe -c "from backend.app.compliance import LegalAcceptanceRepository; print(LegalAcceptanceRepository.__name__)"
```

At the Phase 105F baseline, the command succeeds. The package root uses a lazy `__getattr__` export for `LegalAcceptanceRepository`, so the repository is not imported while the compliance package is still initializing.

Additional import probes also succeed:

```text
.\.venv\Scripts\python.exe -c "from backend.app.persistence.repositories.legal_acceptance_repository import LegalAcceptanceRepository; from backend.app.compliance import LegalAcceptanceService; print(LegalAcceptanceRepository.__name__, LegalAcceptanceService.__name__)"
```

```text
.\.venv\Scripts\python.exe -c "from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator; print(TradeDecisionOrchestrator.__name__)"
```

## Root Cause

The root cause of the original risk was package-root export coupling:

```text
backend.app.compliance
-> compliance service exports
-> persistence repository export
-> compliance model imports
```

If the repository is imported eagerly from the compliance package root, Python can encounter a partially initialized compliance package while the repository imports compliance models.

The current package structure avoids that cycle by keeping repository access lazy at the package root and by using concrete module imports for legal acceptance models.

## Remediation Approach

No compliance source change was required because the active baseline no longer reproduces the circular import failure.

The remediation added targeted regression tests that execute the sensitive imports in a fresh Python interpreter. This ensures future changes cannot accidentally reintroduce eager repository imports or package-root circular initialization.

## Files Changed

```text
tests/test_compliance_imports.py
docs/governance/ITEM_5_COMPLIANCE_CIRCULAR_IMPORT_REMEDIATION.md
```

## Tests Added

The new test coverage verifies:

- compliance package-root `LegalAcceptanceRepository` export imports cleanly
- concrete repository import followed by compliance package import succeeds
- compliance star import preserves the public repository export
- `TradeDecisionOrchestrator` imports without a compliance cycle
- legal acceptance behavior remains fail-closed for missing acceptance

## Tests Executed

Targeted import and behavior test:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_compliance_imports.py -q
```

Security regression:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_security_phase_alpha.py -q
```

Governance legal acceptance regression:

```text
.\.venv\Scripts\python.exe -m pytest tests\governance\test_phase1_legal_acceptance_implementation.py -q
```

## Behavior Preservation

- Compliance logic changed: No.
- Legal acceptance fail-closed behavior preserved: Yes.
- Public imports preserved: Yes.
- Trading behavior changed: No.
- Broker behavior changed: No.
- Dashboard behavior changed: No.
- Risk or margin behavior changed: No.

## Certification Finding

Certification status:

```text
PASS
```

The compliance circular import concern is closed by verification and regression coverage. The known risky import paths now import cleanly, and legal acceptance validation remains fail-closed.
