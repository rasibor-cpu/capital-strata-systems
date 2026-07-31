# DIP-004 - Enterprise Edge Intelligence

**Programme:** CSS Decision Intelligence Platform (DIP)
**Workstream:** DIP-004
**Title:** Enterprise Edge Intelligence
**Status:** IMPLEMENTED - AWAITING REVIEW
**Repository:** `C:\rasib\source\capital-strata-systems`
**Branch:** `css-v1.0.1-maintenance`
**Base HEAD:** `6e408ca1f4e54b8e0dbe0a38ce5144bfff443366`
**Date:** 2026-07-30

**Does not authorize:** desktop runtime access, runtime start/stop, broker access, live market data access, live execution, trade authorization changes, risk-limit changes, sizing changes, capital allocation, strategy optimization, commits, pushes, production release, or OV-002.

**Document authority:** this implementation document is authoritative for DIP-004. `docs/governance/DIP_004_EDGE_INTELLIGENCE_ARCHITECTURE.md` is retained as historical architecture context only and is superseded where this document is more specific.

---

## 1. Architecture

DIP-004 implements an offline, deterministic, advisory-only Edge Intelligence subsystem over:

- Canonical Trade DNA
- Derived metrics
- Evidence graph concepts
- Versioned metadata
- Historical outcomes

It never consumes:

- live market data
- open positions
- runtime state
- current prices
- broker authority
- execution state

Subsystem package:

`backend/intelligence/edge_intelligence/`

| Module | Responsibility |
| --- | --- |
| `models.py` | Edge definitions, candidates, records, evaluations, explanations, lifecycle constants, advisory flags, definition hashes, and edge fingerprints. |
| `discovery.py` | Deterministic discovery of observational historical edge candidates. |
| `evaluation.py` | Deterministic metrics, confidence, thresholds, stability, persistence, and drift. |
| `registry.py` | Persistent Edge Registry with permanent IDs and version history. |
| `reporting.py` | Read-only Edge Intelligence reports. |
| `__init__.py` | Public DIP-004 exports. |

All public payloads carry locked advisory flags:

- `advisory_only=true`
- `execution_allowed=false`
- `capital_movement_allowed=false`
- `broker_action_allowed=false`
- `risk_limit_action_allowed=false`
- `trade_authorization_allowed=false`
- `runtime_control_allowed=false`
- `live_execution_allowed=false`
- `recommendations=false`
- `optimization=false`

---

## 2. EdgeDefinition Contract

`EdgeDefinition` is the immutable semantic definition of an edge.

It owns:

- edge category
- canonical cohort key
- canonical cohort definition
- normalized predicates
- definition version
- optional parent definition hash
- deterministic definition hash

It never owns:

- sample size
- expectancy
- profit factor
- win rate
- confidence
- stability
- persistence
- drift
- lifecycle state
- trade references
- evidence references
- report ordering
- generated timestamps

Definition normalization:

1. String identity components are stripped and uppercased.
2. Dictionaries are serialized with deterministic key ordering.
3. Predicate payloads are normalized before hashing.
4. Display name and description do not own identity.
5. Evidence version and analysis version do not own identity.

The canonical identity key is:

`EdgeDefinition.definition_hash`

The hash prefix is:

`edge-definition:`

---

## 3. EdgeRecord Contract

`EdgeRecord` is the persistent enterprise registry record for a semantic edge definition.

It owns:

- permanent enterprise Edge ID
- definition hash
- serialized edge definition
- current edge fingerprint
- current metrics
- confidence
- stability
- persistence
- drift
- lifecycle
- evidence references
- immutable historical revisions
- relationships
- explanations
- advisory flags

`EdgeRecord` does not own semantic identity. Identity is owned by `EdgeDefinition`.

---

## 4. Registry

The Edge Registry stores persistent `EdgeRecord` entries.

Permanent IDs use the format:

`EDGE-000001`

IDs are assigned deterministically from sorted definition hashes and never change for an existing definition hash.

Permanent ID resolution:

1. `definition_hash` is the primary identity key.
2. Existing definition hash returns the existing permanent Edge ID.
3. New definitions receive the next available permanent Edge ID.
4. New definitions in a batch are sorted by deterministic definition hash before allocation.
5. Discovery order, Trade DNA input order, dictionary order, filesystem order, report order, process ID, random UUIDs, and timestamps cannot affect ID assignment.

Changing expectancy, confidence, stability, drift, evidence version, analysis version, or contributing trades does not create a new Edge ID. Those changes create a new evaluated revision of the same edge.

Each registry record maintains:

- name
- category
- description
- lifecycle state
- created timestamp
- last recalculated timestamp
- analysis version
- evidence version
- edge analysis version
- registry version
- current confidence
- current stability
- current drift
- evidence threshold status
- historical versions
- parent edges
- child edges
- supporting edges
- conflicting edges
- independent edges
- trade references
- evidence references
- explanation references
- advisory flags
- content hash

Persistence uses deterministic JSON ordering and atomic writes.

---

## 5. Definition Hash and Edge Fingerprint

Definition Hash:

- identifies the immutable semantic edge definition
- is derived only from normalized `EdgeDefinition`
- is stable across evidence changes
- is stable across metric changes
- is stable across analysis/evidence version changes unless the semantic definition version itself changes

Edge Fingerprint:

- identifies one evaluated revision of an edge
- includes definition hash
- includes analysis version
- includes evidence version
- includes deterministic contributing Trade DNA references
- includes current evaluated statistics
- includes threshold, confidence, stability, persistence, and drift results

Therefore:

Same definition plus changed evidence produces the same permanent Edge ID and may produce a different Edge Fingerprint.

---

## 6. Historical Evolution

Every changed evaluated revision preserves the previous revision in `historical_versions`.

Each revision records:

- Edge ID
- definition hash
- edge fingerprint
- analysis version
- evidence version
- sample size
- expectancy
- profit factor
- win rate
- average return
- median return
- confidence
- stability
- persistence
- drift
- evidence-threshold result
- lifecycle state
- deterministic evidence references
- supplied recalculation timestamp

Repeated processing of identical evidence and versions does not append duplicate history. Changed evidence, changed metrics, changed evidence version, or changed analysis version may append a new revision while preserving the same permanent Edge ID.

---

## 7. Discovery

Edge Discovery produces observational candidates only. It does not produce recommendations.

Implemented candidate families:

- strategy
- regime
- signal combinations
- holding period
- volatility
- session
- weekday
- entry quality
- exit quality
- risk/reward
- return distributions

Discovery rules:

1. Closed Trade DNA with matching derived metrics only.
2. Inputs sorted by trade ID and DNA ID.
3. Edge definitions are content-hashed from normalized semantic predicates.
4. Unknown or unavailable cohort values are skipped.
5. Discovery never reads runtime state, broker state, live data, current prices, or open positions.

---

## 8. Evaluation

Edge Evaluation computes:

- sample size
- independent observations
- win rate
- loss rate
- profit factor
- expectancy
- median return
- average return
- maximum drawdown
- average holding duration
- median holding duration
- confidence score and label
- stability score and label
- persistence score
- drift score and state
- evidence threshold status
- lifecycle state
- edge fingerprint
- explanation
- counter-evidence

Evidence thresholds are configurable through `EvidenceThresholdPolicy`.

Default posture follows the architecture threshold discipline:

- below threshold remains `BELOW_THRESHOLD`
- partial support remains `OBSERVATIONAL_ONLY`
- supported populations become `SUPPORTED`

---

## 9. Reporting

`EdgeReportBuilder` produces read-only reports with deterministic hashes.

Implemented sections:

- top edges
- weakest edges
- improving edges
- decaying edges
- stable edges
- emerging edges
- strategy comparison
- regime comparison
- holding-time analysis
- signal analysis
- evidence quality

Each edge summary includes:

- trade references
- evidence references
- confidence
- stability
- drift
- explanation
- counter-evidence
- advisory flags

Reports contain no recommendations and no optimization instructions.

---

## 10. Lifecycle

Supported lifecycle states:

- `DISCOVERED`
- `UNDER_OBSERVATION`
- `EVIDENCE_THRESHOLD_MET`
- `STABLE`
- `DRIFTING`
- `DECAYING`
- `ARCHIVED`

Lifecycle changes are observational only.

No lifecycle state can enable or disable a strategy, broker, risk limit, order path, sizing path, or capital path.

---

## 11. Relationships

Registry relationships are informational:

- parent edges
- child edges
- supporting edges
- conflicting edges
- independent edges

Relationship updates preserve permanent IDs and update the record hash.

Relationship integrity rules:

1. Relationships reference permanent Edge IDs only.
2. Self-parent, self-child, self-support, self-conflict, and self-independent references fail validation.
3. Duplicate relationship references collapse deterministically.
4. Relationship ordering is canonical.
5. Unknown Edge IDs fail validation rather than fabricating an edge.

---

## 12. Confidence

Confidence is deterministic and never subjective.

Labels:

- `LOW`
- `MEDIUM`
- `HIGH`
- `VERY_HIGH`

Component scores:

- sample size
- independent observations
- consistency
- variance
- outlier resistance
- recency
- data completeness
- diversity

The weighted confidence model is deterministic from the evaluated historical population.

---

## 13. Stability

Stability evaluates whether an edge persists across chronological windows.

Labels:

- `STABLE`
- `MIXED`
- `UNSTABLE`
- `INSUFFICIENT_HISTORY`

Persistence is reported as the fraction of positive-expectancy chronological windows, adjusted through the stability model.

---

## 14. Drift

Drift compares earlier and recent historical windows.

States:

- `NO_DRIFT`
- `DEGRADING`
- `DECAYING`
- `REGIME_SHIFT`
- `INSUFFICIENT_RECENT_EVIDENCE`

Drift warnings are advisory only and cannot automatically disable strategies or change execution, broker, sizing, risk, runtime, or capital behavior.

---

## 15. Explainability

Every evaluated edge includes an explanation object answering:

- why detected
- which trades contributed
- which DNA records contributed
- which metrics contributed
- why confidence has its label
- why stability has its label
- why drift has its state
- what counter-evidence exists
- what limitations remain

Nothing is emitted as an edge without explanation.

---

## 16. Interfaces

Allowed interfaces:

- Trade DNA records
- Derived trade metrics
- version constants
- deterministic content hashing

Forbidden interfaces:

- ExecutionGate mutation or evaluation paths
- RiskGovernor mutation paths
- AntiBleed mutation paths
- broker routing
- sizing
- capital allocation
- trade authorization
- runtime controls
- live market-data providers
- current price providers
- open-position state

---

## 17. Replay Guarantees and Failure Behavior

Replay guarantees:

1. Same Trade DNA, derived metrics, evidence version, and analysis version produce the same discovered definitions.
2. Shuffled Trade DNA input produces the same definitions.
3. Shuffled discovery candidate order produces the same new-ID allocation for the same unseen definition batch.
4. Registry reload preserves permanent IDs and registry hash.
5. Same evidence does not append duplicate history.
6. Changed evidence appends a new revision without changing permanent Edge ID.

Failure behavior:

1. Unknown relationship IDs raise validation errors.
2. Self relationships raise validation errors.
3. Missing historical derived metrics exclude the trade from edge evaluation.
4. Unknown or unavailable semantic cohort values are skipped.
5. No failure path calls execution, broker, risk, sizing, runtime, or Mission Control mutation surfaces.

---

## 18. Validation

Test file:

`tests/test_dip004_edge_intelligence.py`

Coverage:

- Edge Registry
- Permanent IDs
- Lifecycle
- Version history
- Relationships
- Discovery
- Ranking/reporting
- Confidence
- Evidence thresholds
- Stability
- Persistence
- Drift
- Explainability
- Historical comparisons
- Report determinism
- Replay determinism
- DIP-003 Decision Analytics regression
- EdgeDefinition hash determinism
- Definition Hash versus Edge Fingerprint separation
- stable IDs under shuffled input
- stable IDs under changed metrics, evidence version, and analysis version
- changed evidence appends history
- identical evidence suppresses duplicate history
- execution-facing import exclusion

---

## 19. Future Integration

Permitted future work, with separate authorization:

1. Add offline persistence location for production Edge Registry artifacts.
2. Add read-only Mission Control projection panels.
3. Add broader cohort families once additional Trade DNA fields are populated.
4. Add governance dashboards for evidence quality and drift review.

Still forbidden without a separate governance change:

1. Machine learning.
2. Neural networks.
3. Reinforcement learning.
4. Capital Intelligence.
5. Execution optimization.
6. Strategy optimization.
7. Broker optimization.
8. Risk optimization.
9. Trade automation.
10. Recommendation engine.

---

## 20. Final Recommendation

**READY_FOR_IMPLEMENTATION_REVIEW**

DIP-004 is implemented as an offline, deterministic, advisory-only historical evidence subsystem.

No runtime action is authorized.
No broker action is authorized.
No execution, capital, risk, sizing, or trade authorization behavior is changed by this workstream.

---

*End of DIP_004_EDGE_INTELLIGENCE.md*
