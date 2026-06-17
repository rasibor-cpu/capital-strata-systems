# CSS Runtime Authority Map

## Overview
This document identifies the singular authorities responsible for runtime state, execution, ledger, broker interfaces, and dashboard presentation in Capital Strata Systems (CSS).

## Runtime Ownership
- **Canonical Runtime State Owner**: `backend/app/main.py` and `engine/engine_loop.py`
- **Session State Owner**: `backend/app/auth_manager.py` (and `session_state.json` via governed storage)

## Execution Ownership
- **Canonical Execution Owner**: `backend/orchestration/cross_asset_execution_orchestrator.py`
- **Trade Gate Authority**: `backend/governance/css_unified_trade_gate.py`
- **Execution Validation**: `engine/regime/regime_gate.py` and `backend/app/risk/anti_bleed_guard.py`

## Ledger Ownership
- **Canonical Ledger Owner**: `engine/ledger/pnl_engine.py`
- **Position State Owner**: `backend/app/global_futures_store.py` (Futures), `engine/ledger/ledger_store.py` (Canonical Storage)

## Broker Ownership
- **Canonical Broker Registration**: `backend/app/brokers/broker_registry.py`

## Dashboard Ownership
- **Dashboard Presentation State**: `dashboard/app.py` and `dashboard/mobile_app.py`
- **Summary Presentation**: `dashboard/runtime/summary_builders/pnl_summary_builder.py`
