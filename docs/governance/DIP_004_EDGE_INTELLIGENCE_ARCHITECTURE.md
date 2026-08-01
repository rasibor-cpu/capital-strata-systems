# DIP-004 - Edge Intelligence Architecture

**Programme:** CSS Decision Intelligence Platform (DIP)
**Workstream:** DIP-004
**Title:** Edge Intelligence Architecture
**Status:** ARCHITECTURE COMPLETE - NO IMPLEMENTATION AUTHORIZED
**Repository:** `C:\rasib\source\capital-strata-systems`
**Branch:** `css-v1.0.1-maintenance`
**Base HEAD:** `6e408ca1f4e54b8e0dbe0a38ce5144bfff443366`
**Date:** 2026-07-30

**Does not authorize:** code implementation, desktop runtime access, live market data access, execution changes, broker selection changes, risk-limit changes, trade authorization changes, capital-allocation changes, commits, or production release.

**Historical note:** this architecture document is retained as DIP-004 design context. The authoritative implementation and hardened identity contract are documented in `docs/governance/DIP_004_EDGE_INTELLIGENCE.md`.

---

## 1. Objectives

DIP-004 designs an Enterprise Edge Intelligence architecture that discovers statistically supported trading edges from historical Trade DNA.

The architecture must:

1. Consume only Canonical Trade DNA, derived metrics, evidence graph records, versioned metadata, and historical outcomes.
2. Produce explainable, reproducible, evidence-backed edge conclusions.
3. Keep every output advisory-only.
4. Prevent edge conclusions from influencing execution, capital allocation, broker selection, risk limits, or trade authorization.
5. Separate observational findings from statistically supported edges.
6. Detect stability, persistence, degradation, and drift without automatic strategy disablement.
7. Provide a governed Edge Intelligence Report suitable for later Mission Control projection as read-only intelligence.

---

## 2. Non-Interference Contract

DIP-004 is an analytical architecture only.

Edge Intelligence must never:

| Forbidden action | Rule |
| --- | --- |
| Execution influence | Never call, configure, or mutate ExecutionGate, RiskGovernor, AntiBleed, order routers, broker adapters, or order tickets. |
| Capital allocation | Never resize positions, reweight portfolios, move capital, or set allocation limits. |
| Broker selection | Never select, rank, arm, connect, or change brokers. |
| Risk limits | Never alter drawdown limits, exposure limits, margin limits, stop policy, volatility sizing, or kill-switch state. |
| Trade authorization | Never authorize, deny, pause, enable, or disable trades or strategies. |
| Live data | Never consume current prices, live market data, execution state, open positions, or active broker state. |

All Edge Intelligence records and reports must carry:

| Field | Required value |
| --- | --- |
| `advisory_only` | `true` |
| `execution_allowed` | `false` |
| `capital_movement_allowed` | `false` |
| `broker_action_allowed` | `false` |
| `risk_limit_action_allowed` | `false` |
| `trade_authorization_allowed` | `false` |

---

## 3. Architecture Overview

DIP-004 sits above the Trade DNA and Decision Analytics layers established by DIP-002 and DIP-003.

Logical flow:

1. Trade DNA facts provide immutable trade identity, context, governance, timing, broker-mode metadata, and outcome evidence.
2. Derived metrics provide recomputable analytical values such as return, holding period, expectancy contribution, edge contribution, execution quality, and drawdown contribution.
3. Decision Analytics provides historical cohort features and population summaries.
4. Edge Intelligence groups historical trades into candidate edge populations.
5. Evidence thresholds classify each candidate as `INSUFFICIENT_EVIDENCE`, `OBSERVATIONAL`, `SUPPORTED_EDGE`, or `RETIRED_OBSERVATION`.
6. Confidence, stability, persistence, and drift models score supported populations.
7. The Edge Intelligence Report presents advisory conclusions with evidence citations and explanations.

Domain boundary:

| Layer | Role | Execution authority |
| --- | --- | --- |
| Trade DNA facts | Immutable historical evidence | None |
| Derived metrics | Recomputable historical analytics | None |
| Decision Analytics | Historical cohorts and attribution | None |
| Edge Intelligence | Evidence-backed edge discovery | None |
| Mission Control projection | Read-only reporting surface | None |

---

## 4. Data Flow

### 4.1 Allowed inputs

Edge Intelligence may consume only:

| Input | Purpose |
| --- | --- |
| Canonical Trade DNA | Immutable trade facts and context. |
| Derived metrics | Recomputed outcome, return, holding, drawdown, and quality metrics. |
| Evidence graph | Trade IDs, DNA IDs, versions, sample size, confidence, timestamp, and evidence notes. |
| Versioned metadata | Schema version, analysis version, evidence version, calculation version. |
| Historical outcomes | Closed-trade outcomes and historical labels already sealed in DNA or derived analytics. |

### 4.2 Forbidden inputs

Edge Intelligence must not consume:

| Forbidden input | Reason |
| --- | --- |
| Live market data | Would make Edge Intelligence runtime-sensitive. |
| Execution state | Would allow advisory analytics to observe active trading state. |
| Open positions | Would create capital/risk coupling. |
| Current prices | Would convert historical evidence into live decision support. |
| Broker readiness | Would create broker-selection pressure. |
| Broker credentials | Not needed for historical analysis and forbidden by governance. |
| Runtime authority state | Not needed and could couple analysis to control plane. |

### 4.3 Reproducibility rule

Every edge result must be reproducible from:

1. A fixed set of DNA IDs.
2. A fixed set of derived metric records.
3. A fixed `analysis_version`.
4. A fixed `edge_analysis_version`.
5. A fixed evidence-threshold policy version.
6. A fixed generated-at timestamp for evidence custody, not for metric computation.

No result may depend on wall-clock market state, live price queries, random sampling without seed custody, filesystem ordering, or mutable runtime context.

---

## 5. Edge Lifecycle

Edge Intelligence uses a governed lifecycle so weak observations do not masquerade as durable edge.

| State | Meaning | Permitted output |
| --- | --- | --- |
| `CANDIDATE` | A cohort definition has been discovered or requested. | Internal analytical candidate only. |
| `INSUFFICIENT_EVIDENCE` | Minimum evidence requirements are not met. | Report as insufficient; no edge claim. |
| `OBSERVATIONAL` | Some metrics are visible, but thresholds are incomplete. | May appear in observational appendix. |
| `SUPPORTED_EDGE` | Evidence, confidence, and stability thresholds are met. | May appear in ranked edge sections. |
| `DEGRADING_EDGE` | Previously supported edge shows statistically meaningful decline. | Advisory drift warning only. |
| `UNSTABLE_EDGE` | Edge result is too volatile for a durable conclusion. | Advisory caution only. |
| `RETIRED_OBSERVATION` | Candidate no longer has enough recent evidence or persists only historically. | Historical archive only. |

Transitions:

1. `CANDIDATE` to `INSUFFICIENT_EVIDENCE` when population exists but thresholds fail.
2. `CANDIDATE` to `OBSERVATIONAL` when minimum trade count is present but diversity or confidence fails.
3. `OBSERVATIONAL` to `SUPPORTED_EDGE` when evidence, confidence, stability, and reproducibility pass.
4. `SUPPORTED_EDGE` to `DEGRADING_EDGE` when drift rules detect material degradation.
5. `SUPPORTED_EDGE` to `UNSTABLE_EDGE` when variance or outlier dominance breaches stability thresholds.
6. Any non-supported state to `RETIRED_OBSERVATION` when the candidate is stale or no longer reproducible.

No lifecycle transition may automatically change strategy behavior.

---

## 6. Edge Object Design

An edge is a versioned analytical object representing a historical population whose outcomes are statistically distinguishable from baseline.

Minimum fields:

| Field | Description |
| --- | --- |
| `edge_id` | Stable deterministic ID from category, cohort definition, evidence version, and analysis version. |
| `category` | Edge category, such as strategy, regime, entry, exit, timing, volatility, signal combination, or risk/reward. |
| `description` | Human-readable edge statement without execution instructions. |
| `cohort_definition` | Deterministic filters used to select trades. |
| `trade_population` | Label for the analyzed population. |
| `sample_size` | Number of trades included. |
| `independent_observations` | Count of distinct observation buckets after de-correlation rules. |
| `win_rate` | Winning trades divided by sample size. |
| `loss_rate` | Losing trades divided by sample size. |
| `profit_factor` | Gross profit divided by gross loss, with explicit handling for zero gross loss. |
| `expectancy` | Mean expected result per trade using derived metrics. |
| `average_return` | Arithmetic average return over the population. |
| `median_return` | Median return over the population. |
| `return_dispersion` | Variance or robust dispersion measure. |
| `maximum_drawdown` | Maximum historical drawdown within the population or window. |
| `holding_time` | Average, median, and distribution bucket summary for holding period. |
| `confidence_score` | Deterministic 0.0 to 1.0 score from the confidence framework. |
| `confidence_label` | `LOW`, `MEDIUM`, `HIGH`, or `VERY_HIGH`. |
| `evidence_threshold` | Threshold policy version and pass/fail details. |
| `stability_score` | Deterministic score for cross-window and cross-condition consistency. |
| `persistence_score` | Deterministic score for edge survival across time windows. |
| `drift_state` | `NO_DRIFT`, `WATCH`, `DEGRADING`, `REGIME_SHIFT`, or `INSUFFICIENT_RECENT_EVIDENCE`. |
| `baseline_comparison` | Difference from selected historical baseline. |
| `outlier_impact` | Fraction of result explained by top wins/losses. |
| `data_completeness` | Completeness score for required DNA and derived fields. |
| `last_recalculated` | Evidence custody timestamp. |
| `analysis_version` | Derived metric and analysis version. |
| `edge_analysis_version` | Edge model version. |
| `evidence_version` | Evidence graph version. |
| `trade_references` | Trade IDs and DNA IDs that contributed. |
| `explanation` | Deterministic explanation object. |
| `advisory_flags` | Non-interference flags locked to advisory-only. |

Edge categories:

| Category | Example population |
| --- | --- |
| Strategy Performance | Strategy A in all historical regimes. |
| Regime Performance | Mean-reversion strategy during range-bound regimes. |
| Entry Quality | Breakout entries with high confluence and low spread. |
| Exit Quality | Stop-based exits vs signal-decay exits. |
| Holding-Time | Trades held 30 minutes to 2 hours. |
| Time-of-Day | New York morning session outcomes. |
| Day-of-Week | Tuesday FX trades vs all FX trades. |
| Volatility | Medium-volatility regimes vs high-volatility regimes. |
| Market Regime | Risk-on, risk-off, trend, range, or transition regimes. |
| Signal Combination | Confluence of signal families sealed in DNA. |
| Risk/Reward | Initial reward/risk buckets and realized outcomes. |

---

## 7. Confidence Model

Confidence is a deterministic score, not an analyst opinion.

Labels:

| Label | Score range | Meaning |
| --- | --- | --- |
| `LOW` | 0.00 to 0.39 | Evidence is thin, unstable, incomplete, noisy, or outlier-dominated. |
| `MEDIUM` | 0.40 to 0.64 | Evidence is usable but not strong enough for high-confidence claims. |
| `HIGH` | 0.65 to 0.84 | Evidence is broad, consistent, and complete enough for supported conclusions. |
| `VERY_HIGH` | 0.85 to 1.00 | Evidence is broad, stable, diverse, recent, and robust to outliers. |

Confidence components:

| Component | Purpose |
| --- | --- |
| Sample size score | Rewards larger trade populations with diminishing returns. |
| Independent observation score | Discounts clustered or highly correlated trades. |
| Consistency score | Measures fraction of windows/cohorts with same-sign expectancy. |
| Variance score | Penalizes high dispersion relative to expectancy. |
| Outlier score | Penalizes dependence on a small number of extreme trades. |
| Recency score | Penalizes stale evidence and rewards persistence in recent windows. |
| Completeness score | Penalizes missing required DNA or derived fields. |
| Diversity score | Rewards holding-time, market, regime, symbol, and strategy diversity where relevant. |

Recommended deterministic weighting:

| Component | Weight |
| --- | --- |
| Sample size | 20% |
| Independent observations | 15% |
| Consistency | 20% |
| Variance | 15% |
| Outlier resistance | 10% |
| Recency | 10% |
| Data completeness | 5% |
| Diversity | 5% |

Rules:

1. Confidence cannot exceed `MEDIUM` if sample size is below the supported-edge threshold.
2. Confidence cannot exceed `MEDIUM` if data completeness is below the minimum threshold.
3. Confidence cannot exceed `HIGH` if outlier impact exceeds the maximum threshold.
4. Confidence cannot be `VERY_HIGH` unless stability and persistence both pass.
5. Confidence must expose component scores in the explanation object.

---

## 8. Evidence Thresholds

Evidence thresholds classify a candidate edge before ranking.

Minimum policy:

| Requirement | Observational minimum | Supported edge minimum |
| --- | --- | --- |
| Trade count | 20 | 50 |
| Independent observations | 10 | 30 |
| Positive expectancy windows | 2 | 4 |
| Holding-time diversity | 2 buckets | 3 buckets |
| Market/symbol diversity | 1 market or symbol | 2 markets or symbols when category is not symbol-specific |
| Regime diversity | 1 regime | 2 regimes unless the edge is explicitly regime-specific |
| Data completeness | 80% | 95% |
| Confidence score | 0.40 | 0.65 |
| Outlier dominance | <= 50% result from top 1 trade | <= 30% result from top 3 trades |
| Reproducibility | Required | Required |

Classification:

| Result | Meaning |
| --- | --- |
| `BELOW_THRESHOLD` | Not reportable as an edge. |
| `OBSERVATIONAL_ONLY` | May be shown as a research observation, not a supported edge. |
| `SUPPORTED` | Eligible for ranked edge report sections. |
| `SUPPORTED_WITH_CAUTION` | Meets evidence thresholds but has stability, drift, or concentration warnings. |

Edges below supported threshold remain observational only.

---

## 9. Stability Model

Stability answers whether an edge persists rather than appearing because of one lucky period.

Stability dimensions:

| Dimension | Question |
| --- | --- |
| Time stability | Does expectancy persist across rolling windows? |
| Regime stability | Does the edge survive across relevant regime buckets? |
| Symbol stability | Does the edge depend on one symbol unless explicitly symbol-specific? |
| Strategy stability | Does the edge hold for the intended strategy population? |
| Holding stability | Does the edge survive across holding-time buckets? |
| Outcome stability | Is profit factor resilient to removing top winners and top losers? |

Stability labels:

| Label | Meaning |
| --- | --- |
| `STABLE` | Majority of windows show same-sign expectancy with acceptable variance. |
| `MIXED` | Edge appears in some windows but weakens in others. |
| `UNSTABLE` | Edge conclusion is dominated by volatility, outliers, or narrow conditions. |
| `INSUFFICIENT_HISTORY` | Not enough historical windows to judge stability. |

Persistence score:

1. Split historical trades into chronological windows.
2. Compute expectancy, profit factor, win rate, and drawdown per window.
3. Count same-sign expectancy windows.
4. Penalize periods where drawdown or variance overwhelms expectancy.
5. Penalize stale edges with no recent supporting window.
6. Normalize to 0.0 to 1.0.

---

## 10. Drift Model

Drift detection identifies when a supported edge may be decaying or changing.

Drift types:

| Drift type | Description |
| --- | --- |
| `EDGE_DECAY` | Rolling expectancy, profit factor, or win rate declines materially. |
| `PERFORMANCE_DEGRADATION` | Drawdown, variance, or loss clustering increases. |
| `REGIME_SHIFT` | Edge works only before or after a regime transition. |
| `MARKET_EVOLUTION` | Edge loses support across symbols, sessions, or markets. |
| `VOLATILITY_CHANGE` | Edge sensitivity changes across volatility buckets. |
| `EXPECTANCY_CHANGE` | Mean or median return shifts beyond tolerance. |

Drift states:

| State | Meaning |
| --- | --- |
| `NO_DRIFT` | No material degradation detected. |
| `WATCH` | Early warning; evidence is mixed or recent sample is small. |
| `DEGRADING` | Material negative slope or recent underperformance detected. |
| `REGIME_SHIFT` | Edge changed materially across regime boundary. |
| `INSUFFICIENT_RECENT_EVIDENCE` | Not enough recent observations to evaluate drift. |

Governance rule:

Drift detection must not automatically disable strategies, block trades, change allocations, or alter risk limits. It may only produce advisory warnings and research prompts.

---

## 11. Explainability Model

Every edge must answer:

| Question | Required explanation |
| --- | --- |
| Why was this conclusion produced? | Cohort definition, threshold status, component scores, and ranked metric drivers. |
| Which trades contributed? | Trade IDs and DNA IDs in evidence graph. |
| Which metrics contributed? | Win rate, loss rate, expectancy, profit factor, return distribution, drawdown, holding time, stability, persistence, and drift metrics. |
| What evidence supports it? | Evidence graph node, sample size, versions, timestamps, and threshold results. |
| Why is confidence high? | Component score breakdown showing sample size, consistency, variance, outlier resistance, recency, completeness, and diversity. |
| Why is confidence low? | Explicit failed components and threshold misses. |

Explanation object:

| Field | Description |
| --- | --- |
| `summary` | Plain-language conclusion. |
| `cohort_definition` | Filters and population definition. |
| `metric_drivers` | Ranked metrics that explain the edge. |
| `threshold_results` | Evidence requirements and pass/fail details. |
| `confidence_breakdown` | Component-level confidence scores. |
| `stability_breakdown` | Window, regime, symbol, and holding-time stability details. |
| `drift_breakdown` | Drift tests and state. |
| `supporting_trades` | Trade IDs and DNA IDs. |
| `counter_evidence` | Trades or cohorts that weaken the claim. |
| `limitations` | Missing data, narrow populations, stale windows, or outlier dependence. |
| `reproducibility` | Versions and deterministic inputs required to reproduce. |

Language restrictions:

1. Do not use "buy", "sell", "execute", "increase position", "decrease position", "allocate", "route", or "authorize" as operator instructions.
2. Use "observed", "historically", "evidence suggests", "research attention", and "advisory only".
3. Any edge below threshold must be labeled observational, not supported.

---

## 12. Edge Intelligence Report Design

The Edge Intelligence Report is a read-only artifact generated from historical evidence.

Recommended sections:

| Section | Purpose |
| --- | --- |
| Executive Summary | Advisory status, evidence coverage, supported edge count, warnings. |
| Evidence Coverage | DNA count, derived metric count, date range, completeness, versions. |
| Top Performing Edges | Supported edges ranked by confidence-adjusted expectancy. |
| Weakest Edges | Historically weak or negative-expectancy supported populations. |
| Regime Performance | Edge behavior by regime. |
| Strategy Comparison | Strategy-level expectancy, stability, and confidence. |
| Entry Quality | Historical entry-condition populations. |
| Exit Quality | Historical exit-condition populations. |
| Holding-Time Analysis | Outcome by holding duration buckets. |
| Time-of-Day Analysis | Outcome by session and time bucket. |
| Day-of-Week Analysis | Outcome by weekday. |
| Volatility Analysis | Outcome by volatility bucket. |
| Market-Regime Analysis | Outcome by market regime and transition periods. |
| Signal Combination Analysis | Outcome by historical signal confluence. |
| Risk/Reward Distribution | Initial risk/reward bucket vs realized outcome. |
| Consistency Ranking | Edges ranked by cross-window consistency. |
| Stability Ranking | Edges ranked by stability score. |
| Drift Watchlist | Edges with decay or regime-shift warnings. |
| Evidence Quality | Data completeness, stale evidence, insufficient populations, threshold misses. |
| Observational Appendix | Below-threshold candidates retained for research only. |

Every section must include version metadata and advisory flags.

---

## 13. Interfaces

### 13.1 Internal read interfaces

Future implementation may define read-only interfaces that conceptually map to:

| Interface | Responsibility |
| --- | --- |
| Trade DNA reader | Query immutable DNA by filters and time windows. |
| Derived metrics reader | Query recomputable metrics by DNA ID and analysis version. |
| Decision Analytics reader | Provide cohort summaries and historical attribution views. |
| Evidence graph builder | Bind edge conclusions to trades, versions, confidence, and sample size. |
| Edge report builder | Assemble ranked advisory sections. |

These interfaces must be read-only from Edge Intelligence.

### 13.2 Forbidden interfaces

Edge Intelligence must not import or call interfaces whose purpose is:

| Interface family | Reason |
| --- | --- |
| Broker adapters | Would create broker coupling. |
| ExecutionGate mutation paths | Would create execution coupling. |
| RiskGovernor mutation paths | Would create risk-limit coupling. |
| Position sizing engines | Would create capital allocation coupling. |
| Order routers or order managers | Would create trade authorization coupling. |
| Runtime supervisor controls | Would create runtime authority coupling. |
| Live market-data providers | Would violate historical-only input rule. |

### 13.3 Output interface

Future output contract:

| Artifact | Description |
| --- | --- |
| `EdgeIntelligenceReport` | Complete report payload with sections, evidence, warnings, and metadata. |
| `EdgeRecord` | One edge object with metrics, thresholds, confidence, stability, drift, and explanation. |
| `EdgeEvidenceSummary` | Evidence coverage and reproducibility details. |
| `EdgeObservation` | Below-threshold candidate for research-only appendix. |

All output payloads must be advisory-only.

---

## 14. Future Integration

Permitted future integration:

1. Add read-only Mission Control panels for Edge Intelligence Report sections.
2. Add scheduled offline report generation from sealed DNA artifacts.
3. Add governance review workflows for supported-edge research.
4. Add comparison to historical baselines and prior report versions.
5. Add exportable evidence manifests for audit and certification review.

Forbidden future integration unless a separate governance workstream changes the boundary:

1. Automatic strategy optimization.
2. Machine learning, neural networks, or reinforcement learning.
3. Execution optimization.
4. Capital optimization.
5. Broker optimization.
6. Risk-limit optimization.
7. Live market-data consumption.
8. Trade authorization changes.

---

## 15. Governance Controls

| Control | Requirement |
| --- | --- |
| Versioning | Edge model, threshold policy, evidence graph, and analysis versions must be explicit. |
| Reproducibility | Same DNA IDs and versions must reproduce the same metrics. |
| Evidence custody | Every conclusion must cite trades and DNA IDs. |
| Advisory lock | Every output must carry non-interference flags. |
| Threshold discipline | Below-threshold findings remain observational only. |
| Drift discipline | Drift warnings never trigger automatic control changes. |
| Data isolation | Historical DNA and derived metrics only. |
| Desktop isolation | DIP-004 does not access, start, stop, or synchronize desktop runtime. |

---

## 16. Recommended Validation Plan For Future Implementation

When implementation is authorized in a later phase, validation should prove:

1. Edge records cannot be built without evidence graph trade IDs.
2. Edge records cannot report supported status below thresholds.
3. Confidence labels are deterministic from component scores.
4. Outlier-heavy samples are capped or downgraded.
5. Drift warnings do not mutate strategy, execution, broker, capital, or risk state.
6. Reports are reproducible from fixed DNA and derived metric fixtures.
7. Live market data and open-position inputs are rejected.
8. Output payloads preserve advisory-only flags.

No validation should require runtime startup or broker access.

---

## 17. Final Recommendation

**ARCHITECTURE_READY_FOR_DIP_004_IMPLEMENTATION_REVIEW**

Next authorized step, only if separately approved: implement an offline, read-only Edge Intelligence data model and report builder over existing Trade DNA fixtures and derived metrics.

No code is authorized by this document.
No runtime action is authorized by this document.
No execution, capital, broker, risk, or trade-authorization change is authorized by this document.

---

*End of DIP_004_EDGE_INTELLIGENCE_ARCHITECTURE.md*
