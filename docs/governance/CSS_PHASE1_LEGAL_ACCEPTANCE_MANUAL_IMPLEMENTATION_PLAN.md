# CSS Phase 1 Legal & Trading-Risk Acceptance Manual Implementation Plan

## Current Branch

phase1-lock-candidate-manual

## Confirmed State

Profitability framework: PRESENT  
Risk governance framework: PRESENT  
Legal/trading-risk acceptance authority: MISSING  
Session persistence certification: PENDING  
Phase 1 lock: NOT APPROVED YET

## Required New Components

1. Acceptance model
2. Acceptance store
3. Acceptance version constants
4. Acceptance validation service
5. Login/session enforcement hook
6. Runtime enforcement hook
7. Acceptance audit evidence
8. Governance tests
9. Legal acceptance certification document

## Required Acceptance Types

- LEGAL_TERMS
- TRADING_RISK_DISCLOSURE

## Required Fields

- user_id
- acceptance_type
- acceptance_version
- accepted
- accepted_at
- audit_reference

## Required Validation Rules

Missing acceptance = BLOCK  
Invalid acceptance = BLOCK  
Outdated acceptance = BLOCK  
Current valid acceptance = ALLOW

## Required Files To Create

Suggested:

backend/app/compliance/legal_acceptance.py
backend/app/compliance/legal_acceptance_store.py
backend/app/compliance/legal_acceptance_versions.py
backend/app/compliance/legal_acceptance_service.py
tests/governance/test_phase1_legal_acceptance_implementation.py
docs/governance/CSS_PHASE1_LEGAL_ACCEPTANCE_IMPLEMENTATION.md

## PCNRASS Rules

No broker changes.  
No live execution changes.  
No dashboard authority changes.  
No PnL changes.  
No governance weakening.  
No runtime refactoring outside acceptance validation.  
Additive changes only where possible.

## Next Implementation Order

1. Create compliance package.
2. Add version constants.
3. Add acceptance record dataclass/model.
4. Add durable JSON or SQLite-backed store.
5. Add validation service.
6. Add tests for missing/invalid/outdated/current acceptance.
7. Add audit event placeholder/reference.
8. Add certification document.
9. Re-run governance tests.
10. Certify session persistence separately.