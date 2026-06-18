# CSS Broker Authority Map

## Overview
This map tracks the singular flow of broker authority to guarantee governed execution.

## Canonical Data Flow
Broker Adapter → Execution Layer → Runtime → Ledger → Dashboard

## Supported Brokers

### 1. OANDA (FX)
- **Broker Adapter**: `backend/app/brokers/oanda_adapter.py`
- **Execution Layer**: `cross_asset_execution_orchestrator.py`
- **Runtime**: `engine_loop.py`
- **Ledger**: `pnl_engine.py`
- **Dashboard**: `dashboard/app.py` / `dashboard/mobile_app.py`

### 2. Coinbase (Crypto)
- **Broker Adapter**: `backend/app/brokers/coinbase_adapter.py`
- **Execution Layer**: `cross_asset_execution_orchestrator.py`
- **Runtime**: `engine_loop.py`
- **Ledger**: `pnl_engine.py`
- **Dashboard**: `dashboard/app.py` / `dashboard/mobile_app.py`

### 3. IBKR (Equities/Derivatives)
- **Broker Adapter**: `backend/app/brokers/ibkr_adapter.py`
- **Execution Layer**: `cross_asset_execution_orchestrator.py` (Note: Options and Futures execution explicitly disabled pending live approval)
- **Runtime**: `engine_loop.py`
- **Ledger**: `pnl_engine.py`
- **Dashboard**: `dashboard/app.py` / `dashboard/mobile_app.py`

### 4. Paper Broker (Simulation)
- **Broker Adapter**: `backend/app/brokers/paper_broker.py` (and sim adapters like `futures_sim_adapter.py`)
- **Execution Layer**: `cross_asset_execution_orchestrator.py`
- **Runtime**: `engine_loop.py`
- **Ledger**: `pnl_engine.py`
- **Dashboard**: `dashboard/app.py` / `dashboard/mobile_app.py`
