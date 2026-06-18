# CSS Phase 1B Legal Acceptance Enforcement Integration

## Purpose

This document defines the Phase 1B integration point for legal and trading-risk acceptance enforcement within Capital Strata Systems (CSS).

The objective is to ensure that no trading-enabled session can be marked ready unless all required legal acceptances have been validated.

This implementation is additive and PCNRASS-compliant.

---

## Authority

Primary enforcement authority:

backend.app.compliance.legal_acceptance_enforcement.enforce_trading_session_acceptance

This helper is the sole Phase 1B acceptance enforcement gate.

---

## Integration Point

Acceptance validation shall occur:

1. After authenticated user identity is established.
2. Before a trading-enabled session is marked ready.
3. Before access is granted to live, paper, or practice trading workflows.

---

## Fail-Safe Behavior

Trading-enabled readiness shall be blocked when:

- Legal Terms acceptance is missing.
- Trading Risk Disclosure acceptance is missing.
- Acceptance records are invalid.
- Acceptance versions are outdated.
- User identity cannot be validated.

The default outcome is BLOCK.

---

## Allowed Behavior

Trading-enabled readiness shall be allowed only when:

- Legal Terms acceptance is current.
- Trading Risk Disclosure acceptance is current.
- Acceptance records are valid.
- User identity is confirmed.

---

## Non-Trading Modes

The following modes may proceed without acceptance enforcement:

- Simulation
- Demo
- Analytics
- Reporting

These modes must not grant trading authority.

---

## Dashboard Authority

Dashboard components are not acceptance authorities.

Dashboard state, reporting state, analytics state, or UI indicators must never override acceptance enforcement decisions.

---

## PCNRASS Compliance

This implementation:

- Does not modify broker adapters.
- Does not modify execution adapters.
- Does not modify live trading logic.
- Does not modify dashboard authority.
- Does not modify PnL calculations.
- Does not weaken governance controls.

The implementation is additive only.

---

## Validation Requirements

Required validation outcomes:

- Missing legal acceptance -> BLOCK
- Missing trading-risk acceptance -> BLOCK
- Invalid acceptance -> BLOCK
- Outdated acceptance -> BLOCK
- Current legal + trading-risk acceptance -> ALLOW

---

## Certification Status

Phase 1B Enforcement Helper:
Implemented

Runtime Integration:
Pending

Persistent Storage Integration:
Pending

Production Certification:
Pending