# CSS Simulator & Academy Foundation

## Purpose

CSS Simulator & Academy provides a low-risk onboarding and learning path built on deterministic simulation rather than broker execution.

Progression model:

**Learn -> Simulate -> Broker Read-Only -> Advisory -> Controlled Live**

This foundation intentionally implements only the first two stages.

## Safety boundary

The simulator:

- has no broker credentials;
- makes no network calls;
- has no order-routing surface;
- cannot transfer, withdraw, deposit, or fund money;
- cannot create a live broker order;
- rejects naked/short simulated sells in the foundation implementation;
- marks every accepted fill as simulated.

It is an educational and product-training layer, not a live execution adapter.

## Foundation capabilities

### Deterministic simulated portfolio

The engine tracks:

- cash;
- long positions;
- average cost;
- mark-to-market value;
- realized P&L;
- unrealized P&L;
- total equity;
- high-water mark;
- drawdown.

Monetary values use `Decimal`.

### Academy scoring

The initial scoring model exposes:

- simulated return;
- benchmark excess return;
- drawdown;
- decision-quality score;
- capital-preservation status.

### Challenges and badges

The first challenge families are:

- capital preservation;
- benchmark outperformance;
- drawdown control;
- decision discipline.

Badges derive only from completed challenges.

### Forecast presentation contract

Forecasts are represented probabilistically. They include:

- probability up / flat / down;
- expected range;
- confidence;
- explicit invalidation condition.

CSS should not present future market outcomes as certainty.

## Deliberate separation from QRO

This package is broker-independent and does not depend on the QRO-002X/QRO-003X code that currently exists only in the newer local worktree.

When that worktree is pushed, the simulator can consume its canonical replay/portfolio interfaces through a thin adapter. The simulator must remain a separate domain layer so that simulation actions can never be mistaken for broker instructions.

## Next increments

1. scenario/replay adapter to the canonical QRO portfolio model;
2. learning curriculum and lesson progression;
3. richer challenge catalog;
4. recommendation accept/reject journaling;
5. benchmark service;
6. simulator API projection and mobile UI;
7. achievement history and optional leaderboards;
8. explicit readiness gates before any transition beyond advisory mode.
