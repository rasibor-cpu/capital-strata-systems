# CSS Phase 1 Legal & Trading-Risk Acceptance Implementation

## Status

Phase 1 lock remains **not approved** until legal and trading-risk acceptance
validation is implemented, tested, reviewed, and certified alongside the pending
session persistence certification.

Confirmed current state:

* Profitability framework: **PRESENT**
* Risk governance framework: **PRESENT**
* Legal/trading-risk acceptance authority: **IMPLEMENTED BY THIS PACKAGE**
* Session persistence certification: **PENDING**
* Phase 1 lock: **NOT APPROVED YET**

## Scope

This implementation introduces an additive backend compliance authority for
manual Phase 1 legal and trading-risk acceptance validation.

The authority covers two required acceptance types:

1. `LEGAL_TERMS`
2. `TRADING_RISK_DISCLOSURE`

Each acceptance record requires the following fields:

* `user_id`
* `acceptance_type`
* `acceptance_version`
* `accepted`
* `accepted_at`
* `audit_reference`

## Validation Rules

The Phase 1 legal acceptance authority enforces the following outcomes:

| Condition                | Result  |
| ------------------------ | ------- |
| Missing acceptance       | `BLOCK` |
| Invalid acceptance       | `BLOCK` |
| Outdated acceptance      | `BLOCK` |
| Current valid acceptance | `ALLOW` |

A user is allowed by the aggregate Phase 1 acceptance check only when both
required acceptance types are present, accepted, current-version, and valid.

## Proposed Architecture

The implementation is intentionally small and authority-scoped:

```text
backend/app/compliance/
├── __init__.py
├── legal_acceptance_versions.py
├── legal_acceptance.py
├── legal_acceptance_store.py
└── legal_acceptance_service.py
```

## Module Responsibilities

### legal_acceptance_versions.py

Defines the canonical required acceptance types and current required versions.

This module is the version authority for:

* `LEGAL_TERMS`
* `TRADING_RISK_DISCLOSURE`

### legal_acceptance.py

Defines immutable domain objects and validation result types:

* `LegalAcceptanceRecord`
* `AcceptanceValidationResult`
* `AcceptanceValidationStatus`
* `AcceptanceBlockReason`

### legal_acceptance_store.py

Defines the acceptance storage boundary.

Current Phase 1 implementation:

* `InMemoryLegalAcceptanceStore`

Future durable implementation may replace or supplement this store without
changing validation semantics.

### legal_acceptance_service.py

Defines the service authority:

* Records legal/trading-risk acceptance decisions.
* Validates one acceptance type.
* Validates all required Phase 1 acceptances.
* Blocks missing, invalid, and outdated acceptance.
* Allows only current valid acceptance.

## PCNRASS Compliance Review

This implementation is PCNRASS-aligned because it is additive and does not alter
existing trading authorities or runtime execution pathways.

| PCNRASS Constraint                                   | Compliance Position |
| ---------------------------------------------------- | ------------------- |
| No broker changes                                    | Compliant           |
| No live execution changes                            | Compliant           |
| No dashboard authority changes                       | Compliant           |
| No PnL changes                                       | Compliant           |
| No governance weakening                              | Compliant           |
| No runtime refactoring outside acceptance validation | Compliant           |
| Additive changes only where possible                 | Compliant           |

## Authority Boundary

The legal acceptance service is a validation authority.

It does **not**:

* execute trades
* place orders
* mutate broker state
* calculate PnL
* override risk governors
* override broker gates
* grant dashboard authority

The intended integration pattern is for existing guarded entry points to query
the service before allowing a user into Phase 1 trading-enabled workflows.

## Integration Points

Recommended future integration points:

1. Authentication/session readiness
   Validate required acceptances after user identity is known.

2. Runtime access gate
   Block trading-enabled runtime access if required acceptance is missing,
   invalid, or outdated.

3. Audit trail
   Persist `audit_reference` with each acceptance decision.

4. Durable persistence
   Replace or supplement `InMemoryLegalAcceptanceStore` with a database-backed
   implementation before final production lock.

## Implementation Risks

### 1. Persistence Gap

The in-memory store is deterministic and testable but not durable.

Mitigation:

* Add a database-backed legal acceptance store.
* Preserve append-only acceptance records.
* Retain current validation semantics.

### 2. User Identity Binding Risk

Acceptance records are meaningful only when `user_id` is canonical and stable.

Mitigation:

* Integrate only after authenticated identity resolution.
* Do not allow dashboard-supplied display names to act as acceptance authority.

### 3. Version Drift Risk

If legal terms or trading-risk disclosure content changes without updating
current acceptance versions, stale acceptances may incorrectly remain valid.

Mitigation:

* Require governance review for version changes.
* Update `CURRENT_ACCEPTANCE_VERSIONS` whenever legal/risk content changes.

### 4. Audit Reference Quality Risk

The `audit_reference` field is required but its format is intentionally generic.

Mitigation:

* Define a production audit reference convention before lock approval.
* Link references to immutable audit records or retained acceptance events.

## Recommended Next Steps

1. Run the new governance test.
2. Run the full governance test suite.
3. Compile the new compliance package.
4. Add durable persistence.
5. Integrate with authenticated session readiness.
6. Certify session persistence.
7. Perform final Phase 1 release certification.

## Manual Validation Commands

Run these from the repository root:

```bash
python -m py_compile backend/app/compliance/__init__.py
python -m py_compile backend/app/compliance/legal_acceptance_versions.py
python -m py_compile backend/app/compliance/legal_acceptance.py
python -m py_compile backend/app/compliance/legal_acceptance_store.py
python -m py_compile backend/app/compliance/legal_acceptance_service.py
pytest tests/governance/test_phase1_legal_acceptance_implementation.py
pytest tests/governance
```

## Final Position

This package closes the first implementation layer for the Phase 1 legal and
trading-risk acceptance authority.

Phase 1 lock remains pending until:

* durable acceptance persistence is added or formally deferred,
* acceptance validation is integrated with authenticated session readiness,
* session persistence certification is completed,
* final Phase 1 release certification passes.
