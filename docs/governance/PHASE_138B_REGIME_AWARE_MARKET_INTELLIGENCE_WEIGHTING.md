# CSS Phase 138B - Regime-Aware Market Intelligence Weighting

Phase 138B adds deterministic weighting to the Phase 138A market intelligence layer.
The output remains advisory only and never grants execution authority.

## Purpose

The weighting engine adjusts how much influence technical analysis, fundamental analysis,
sentiment intelligence, and quantitative alpha have in the final multi-factor signal.
Weights adapt to the current market regime, portfolio lifecycle context, and optional
policy profile.

## Regime Methodology

- Unknown regimes use balanced weights: technical 25, fundamental 25, sentiment 25,
  quantitative 25.
- Trending regimes increase technical and quantitative weights.
- High-volatility regimes increase sentiment and risk-aware quantitative emphasis.
- Macro and risk-off regimes increase fundamental and sentiment weights.
- Missing components receive zero weight and the remaining weights are normalized to
  exactly 100.0.

## Confidence Adjustment

The engine emits a confidence adjustment from -100 to +100. Missing components reduce
confidence. No-portfolio, startup, initializing, or unknown portfolio context reduces
confidence but does not fail the system when other market intelligence is available.

## Advisory-Only Operation

Every package returns:

```python
{
    "advisory_only": True,
    "execution_allowed": False,
}
```

The engine does not read broker credentials, submit orders, enable live trading, bypass
RBAC, weaken risk gates, or alter Runtime Supervisor, Unified Trade Gate, Capital Governor,
AntiBleedGuard, or Portfolio Risk Committee decisions.

## API And Dashboard

`GET /api/regime-aware-weighting` returns the weighting package.
`GET /api/multi-factor-signal` includes the weights, weighting reasons, and confidence
adjustment used by the synthesizer.

The mobile dashboard Market Intelligence section displays regime-aware weights, weighting
reasons, weighted multi-factor score, and confidence adjustment with safe `DATA UNAVAILABLE`
fallback behavior.
