# CSS Simulator & Academy — Phase 3

Phase 3 makes the academy durable and session-oriented while remaining entirely simulation-only.

## Delivered

- atomic learner-profile persistence;
- idempotent lesson, decision, achievement, and challenge history;
- deterministic scenario catalog;
- benchmark return/excess-return engine;
- mobile-facing session state built from learner + scenario + scoring state.

## Learner profile

The persisted profile contains only academy data:

- learner ID;
- completed lesson IDs;
- recommendation decisions;
- achievements;
- challenge observation counts;
- update timestamp.

It contains no broker credentials, brokerage account identifiers, authorization headers, or payment data.

Writes use a temporary file followed by atomic replacement.

## Scenario catalog

Initial deterministic scenarios:

1. steady uptrend;
2. drawdown and recovery;
3. range with false breakout.

Each scenario includes a learning objective, starting cash, a deterministic instrument price path, and a benchmark path.

## Benchmarking

The benchmark engine calculates total return and learner excess return using Decimal arithmetic.

## Mobile-facing session state

A session projection combines:

- learner progress;
- scenario status;
- benchmark state;
- portfolio/scoring projection;
- challenges;
- achievements;
- recommendation journal.

Every session projection remains explicitly:

- SIMULATION mode;
- execution disabled;
- broker execution unarmed;
- money movement disabled.

## Boundary

No broker adapter, live order surface, transfer, withdrawal, funding, deposit, or credential logic is introduced by Phase 3.
