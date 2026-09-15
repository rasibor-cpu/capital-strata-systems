# CSS Enterprise Program B — Monte Carlo Outcome Simulation

## Status

IMPLEMENTED — RESEARCH ONLY

## Purpose

This increment adds deterministic bootstrap Monte Carlo simulation for strategy
research and portfolio validation.

## Implemented outputs

- median terminal return;
- 5th-percentile terminal return;
- 95th-percentile terminal return;
- probability of loss;
- median maximum drawdown;
- 95th-percentile maximum drawdown.

Simulation resamples supplied historical returns using an explicit seed, making
CI and certification evidence reproducible.

## Fail-closed rules

Simulation rejects:

- fewer than two historical observations;
- non-finite returns;
- returns at or below -100%;
- non-positive path counts;
- non-positive horizons.

## Safety boundary

Monte Carlo results are `RESEARCH_ONLY`.

They do not authorize:

- live trading;
- broker execution;
- capital deployment;
- order submission;
- money movement;
- automatic strategy promotion.

## Next Program B gaps

1. experiment registry and research approval workflow;
2. consolidated institutional research package/export.
