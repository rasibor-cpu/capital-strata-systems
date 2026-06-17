# PHASE 97E: PORTFOLIO MARGIN HISTORICAL TRACKING

## Objective
Establish a read-only historical tracking layer for portfolio margin risk states. This phase records snapshots over time to observe margin stress trends before future execution authority is granted.

## Read-Only Governance Policy
This phase is exclusively a monitoring and evidence-capture implementation.
- No execution authority is granted.
- No broker behavior is changed.
- No risk gate behavior is changed.
- No order-routing behavior is changed.

## Authoritative Data Flow
The framework stores the `PortfolioMarginSnapshot` and the `PortfolioMarginRiskMonitor` output exactly as computed. No synthetic values or extra derivations are created.

## Storage Specifications
- **Format:** Local JSONL storage.
- **Location:** `artifacts/portfolio_margin_history/`
- **Files:**
  - `portfolio_margin_snapshots.jsonl`
  - `portfolio_margin_risk_events.jsonl`
- **Behavior:**
  - Strict append-only tracking.
  - No file overwrites or truncations.
  - Explicit failure if the provided payloads are invalid or malformed.
