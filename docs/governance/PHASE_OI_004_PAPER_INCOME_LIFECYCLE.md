# Phase OI-004 - Paper Income Lifecycle Engine

Date: 2026-07-14

Branch: `css-unified-consolidation-2026-07-13`

## Purpose

Phase OI-004 adds a deterministic paper-only lifecycle engine for accepted Options Income Engine candidates. It consumes OI-003 accepted covered-call and cash-secured-put candidates and their OI-002 strategy summaries, then tracks paper position state, premium accounting, collateral reservation/release, expiration outcomes, assignment simulation, and immutable lifecycle event history.

This phase is advisory and paper-only. It never authorizes live execution, places orders, cancels orders, modifies broker state, arms execution, or enables live trading.

## Architecture

The implementation is split into small broker-neutral modules:

- `backend/options/paper_income_lifecycle.py` coordinates accepted candidate ingestion, lifecycle transitions, collateral, premium accounting, expiration, and completion.
- `backend/options/paper_position_repository.py` stores paper income positions and immutable event payloads in memory or an optional JSON repository.
- `backend/options/position_state_machine.py` defines the allowed lifecycle graph and rejects invalid transitions.
- `backend/options/premium_accounting.py` calculates received, realized, and remaining premium plus yield metrics.
- `backend/options/collateral_manager.py` reserves and releases paper share/cash collateral.
- `backend/options/expiration_engine.py` evaluates expiry processing without broker calls.
- `backend/options/assignment_simulator.py` produces deterministic paper outcomes for worthless expiry, assignment, exercise, and early close.

## Lifecycle

The valid state path is:

`DISCOVERED -> APPROVED -> PAPER_OPEN -> ACTIVE -> EXPIRING -> EXPIRED_WORTHLESS|ASSIGNED|EXERCISED|CLOSED_EARLY -> COMPLETED`

Invalid transitions fail closed. Completed positions cannot be reprocessed. Early close is modeled as a paper lifecycle outcome and does not send a broker instruction.

## Premium Accounting

Premium accounting tracks:

- premium received
- premium realized
- premium remaining
- yield
- yield on collateral
- annualized yield
- capital efficiency

Negative premium, malformed values, and invalid collateral inputs are rejected.

## Collateral Management

Covered calls reserve paper shares. Cash-secured puts reserve paper cash. The collateral manager rejects negative collateral, zero collateral, duplicate reservations, missing records, and double releases.

## Expiration And Assignment

Expiration processing evaluates expiry date, intrinsic value, strategy type, and underlying price. Outcomes are deterministic:

- `EXPIRED_WORTHLESS`
- `ASSIGNED`
- `EXERCISED`
- `CLOSED_EARLY`

Collateral is released, premium is finalized, and lifecycle events are appended before the position reaches `COMPLETED`.

## Safety Guarantees

OI-004 preserves these advisory-only flags throughout the lifecycle:

- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`

The modules do not import broker adapters, execution adapters, credential modules, live runtime controls, or order-routing surfaces.

## Fail-Closed Behavior

The engine rejects:

- missing candidates
- rejected OI-003 candidates
- missing or rejected OI-002 strategy summaries
- unsupported strategies
- malformed contracts or quantities
- duplicate positions
- invalid lifecycle transitions
- negative premium
- negative collateral
- double collateral reservation
- double collateral release
- repository corruption
- invalid timestamps
- completed-position reprocessing

## Relationship To Earlier OI Phases

OI-002 defines covered-call and cash-secured-put strategy summaries, collateral requirements, payoff/risk fields, and advisory-only flags.

OI-003 ranks accepted income opportunities using canonical option contracts and OI-002 builders.

OI-004 starts only after OI-003 has accepted a candidate and after the OI-002 summary is present and valid.

## Out Of Scope

This phase does not implement:

- live options broker integration
- order entry
- order cancellation
- rolling orders
- exercise instructions
- broker assignment notice ingestion
- dashboard activation
- runtime execution authority

## Validation

Primary validation is covered by `tests/test_oi004_paper_income_lifecycle.py`, plus OI-002/OI-003 and options execution/lifecycle regressions.
