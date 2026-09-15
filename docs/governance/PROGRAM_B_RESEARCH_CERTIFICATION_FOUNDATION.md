# CSS Enterprise Program B — Research Certification Foundation

## Status

IMPLEMENTED — SHADOW/RESEARCH GOVERNANCE ONLY

## Audit result

Program B is not starting from zero. The repository already contains:

- a historical backtest engine;
- walk-forward optimisation support;
- portfolio stress-testing architecture and tests;
- performance analytics;
- CAIE portfolio optimisation and learning infrastructure;
- prior correlation-intelligence architecture.

The principal gap addressed by this increment is a canonical, fail-closed
research-evidence certification contract that can sit above those components
without modifying trading behavior.

## Implemented

This increment adds:

- immutable `ResearchEvidence`;
- benchmark-relative excess-return calculation;
- minimum sample/trade thresholds;
- out-of-sample requirement;
- walk-forward depth requirement;
- drawdown, Sharpe and profit-factor thresholds;
- explicit stress-test requirement;
- explicit data-quality requirement;
- fail-closed evidence validation;
- `CERTIFIED_SHADOW`, `REVIEW_REQUIRED`, and
  `REJECTED_INVALID_EVIDENCE` decisions.

## Safety boundary

A successful certification means only that the research package may be used in
shadow/advisory research workflows.

It does **not** authorize:

- live trading;
- broker execution;
- order submission;
- money movement;
- capital deployment;
- automatic strategy promotion.

`approved_for_live=false` is invariant.

Human approval remains required.

## Next Program B gaps

The next bounded increments should address, in order:

1. canonical dataset/data-quality evidence;
2. deterministic benchmark comparison;
3. correlation calculation and concentration analytics;
4. Monte Carlo outcome simulation;
5. experiment registry and research approval records;
6. consolidated institutional research package/export.

Existing architecture should be reused rather than duplicated.
