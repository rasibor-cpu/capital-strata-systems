# Phase 131 Quantitative Intelligence

## Purpose

Phase 131 adds dependency-free quantitative analytics to strengthen the CSS portfolio intelligence layer. It computes portfolio metrics from deterministic input series and exposes the results through advisory-only API and dashboard surfaces.

## Advisory-Only Design

Quantitative Intelligence does not place orders, approve trades, change allocation state, enable live trading, or alter any risk gate. It produces evidence for human and governance review only.

The added metrics include:

- rolling Sharpe
- rolling Sortino
- Calmar ratio
- Omega ratio
- Information ratio
- Alpha and Beta
- correlation matrix
- max drawdown
- drawdown distribution
- volatility
- downside deviation

## Data Insufficiency Handling

When return series are missing, malformed, or too short, the engine returns `DATA UNAVAILABLE` with clear reasons. It does not infer missing broker/live data and does not synthesize trading authority.

## Relationship To Phase 129D And Phase 130

Phase 129D established portfolio intelligence and capital rotation. Phase 130 added adaptive portfolio and risk committee synthesis. Phase 131 adds quantitative evidence that can inform those advisory layers without changing their execution boundaries.

## Execution Authority

No broker behavior, live-trading behavior, Unified Trade Gate behavior, Capital Governor behavior, Runtime Supervisor behavior, RBAC behavior, AntiBleedGuard behavior, or Portfolio Risk Committee authority was weakened or bypassed.

## Future Path

The quantitative metrics may support supervised automation in a later phase, but Phase 131 does not enable automation. Future automation would require explicit governance approval and must remain subordinate to existing execution and risk authorities.
