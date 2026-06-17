# CSS Dashboard Dependency Map

## Overview
This map classifies all dashboard components by their interaction with canonical runtime state.

## Dashboard Components

### 1. `dashboard/app.py` (Desktop Dashboard)
- **Classification**: `READ_ONLY`
- **Data Sources**: Canonical PnLSnapshot, read-only runtime state exports
- **Justification**: Does not directly execute trades or mutate ledger state.

### 2. `dashboard/mobile_app.py` (Mobile Interface)
- **Classification**: `READ_ONLY`
- **Data Sources**: Canonical PnLSnapshot via `pnl_summary_builder.py`
- **Justification**: Direct REST execution has been removed; routes cleanly through `TradeDecisionOrchestrator` for purely read-only state summaries.

### 3. `dashboard/runtime/summary_builders/pnl_summary_builder.py`
- **Classification**: `READ_ONLY`
- **Data Sources**: `engine.ledger.pnl_engine.PnLEngine` output maps
- **Justification**: Aggregates output data explicitly without mutating canonical state (Phase 105B).

### 4. `dashboard/runtime/summary_builders/trade_status_builder.py`
- **Classification**: `READ_ONLY`
- **Data Sources**: Orchestrator state and ledger
- **Justification**: Used strictly for presentation.

## Deprecated Components
- Legacy ad-hoc PnL loops: `DEPRECATED` and `VIOLATION` (removed from active dashboard paths).
