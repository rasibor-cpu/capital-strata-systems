# CSS Code Duplication Analysis

This analysis inventories duplicated logic, redundant helpers, and boilerplate mappings across the CSS codebase.

---

## 1. Inventory of Duplicate Logic

### Normalization and Type Coercion Helpers
- **Redundant Helper**: `safe_float` and `clamp`.
- **Instances**:
  - `backend/portfolio/utils.py`: Defines `safe_float()` and `clamp()`.
  - `backend/intelligence/committee_member_models.py`: Imports and re-implements local scaling.
  - `backend/reporting/executive_recommendations.py`: Redefines scaling/safe converters.
  - `analytics_harness.py`: Defines separate float parser.

### Advisory Payload Structures (Safety Flags)
- **Boilerplate Boilerplate**: Explicit definition of advisory disarming dictionaries.
- **Instances**:
  - `backend/portfolio/utils.py`: `advisory_response()` and `_safety_flags()`.
  - `backend/portfolio/portfolio_construction_intelligence.py`: `_safety_flags()`.
  - `backend/intelligence/investment_committee_engine.py`: `_fail_closed()`.
  - `backend/reporting/executive_decision_brief.py`: `_fail_closed()`.

### Resilience & Risk Metric Evaluations
- **Redundant Metrics**: Calculations of drawdown metrics.
- **Instances**:
  - `backend/portfolio/portfolio_resilience_analyzer.py`: Computes drawdown scores.
  - `backend/portfolio/diversification_optimizer.py`: Redefines drawdown bounds.

### JSON Formatting & Printing
- **Format Boilerplate**: Format schemas.
- **Instances**:
  - `backend/runtime/broker_health_monitor.py`: Custom formatting block.
  - `backend/reporting/executive_summary_formatter.py`: Specialized JSON output formatter.

---

## 2. Refactoring Strategy

To remove duplicates safely without altering public APIs or execution rules:
1. **Centralize Utilities**:
   - Merge `safe_float` and numeric bounds checks into a centralized helper `backend/common/utils.py`.
2. **Standardize Safety Dictionaries**:
   - Expose a single immutable payload builder for all advisory layers in `backend/common/safety.py` that sets all disarm metrics.
3. **Consolidate Metric Computation**:
   - Relocating drawdown estimations to `backend/analytics/metrics.py`.
