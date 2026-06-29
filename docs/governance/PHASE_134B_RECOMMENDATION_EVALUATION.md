# Phase 134B Recommendation Evaluation

## Purpose

Phase 134B adds deterministic evaluation of historical advisory recommendations against later portfolio outcomes. The framework is evidence-driven and read-only. It does not place orders, alter broker behavior, change live trading controls, or modify governance gates.

## Methodology

The recommendation evaluator consumes evaluated advisory history records that include:

- recommendation direction
- confidence
- policy profile
- market regime
- asset class
- strategy
- subsequent outcome return or drawdown

Recommendations are classified as defensive, aggressive, or neutral. A defensive recommendation is considered correct when later returns are non-positive or drawdown is elevated. An aggressive recommendation is considered correct when later returns are positive without excessive drawdown. A neutral recommendation is considered correct when performance remains within a narrow tolerance.

The engine computes:

- overall recommendation accuracy
- precision and recall for aggressive recommendations
- confidence calibration score
- avoided-loss estimate
- missed-opportunity estimate
- recommendation effectiveness
- accuracy by policy profile, market regime, asset class, strategy, and recommendation type

## Fail-Closed Behavior

If evaluated history is absent, malformed, or lacks subsequent outcomes, the evaluator returns `DATA UNAVAILABLE`. It does not infer results from unevaluated recommendations.

All outputs include advisory-only metadata and explicitly disallow execution.

## Limitations

The estimates are deterministic proxies, not causal proof. Avoided loss and missed opportunity are based on observed forward outcomes and recommendation direction. They should be interpreted as monitoring evidence, not trading instructions.

## Future Machine-Learning Opportunities

Future work may compare deterministic thresholds with offline model-based calibration. Any such work must remain advisory-only unless separately approved through CSS governance and safety review.
