# Phase 129D Portfolio Intelligence

## Scope

The Portfolio Intelligence Engine provides deterministic, read-only analysis of portfolio evidence for dashboard and API consumers.

## Inputs

- Open portfolio positions
- Exposure values by symbol and asset class
- Performance metrics including drawdown, Sortino, capital efficiency, concentration, and correlation

## Outputs

- Portfolio intelligence score
- Portfolio status: `HEALTHY`, `WATCH`, or `DEFENSIVE`
- Advisory recommendation: `MAINTAIN`, `REBALANCE`, `REDUCE_RISK`, or `NO_ACTION`
- Explainability messages for each applied penalty
- Read-only asset-class and symbol exposure percentages

## Safety

- No broker calls
- No order submission
- No live-trading enablement
- No Runtime Supervisor changes
- No Unified Trade Gate changes
- No Capital Governor changes
- Fail-closed `DATA UNAVAILABLE` output when required evidence is missing or malformed

## Penalty Model

The engine penalizes:

- High drawdown
- Weak Sortino
- Poor capital efficiency
- High concentration
- Excessive correlation

The output is advisory only and does not alter trading behavior.
