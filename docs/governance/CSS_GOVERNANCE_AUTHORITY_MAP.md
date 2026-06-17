# CSS Governance Authority Map

## Overview
This map classifies the major governance files and modules across the CSS infrastructure.

## Governance Modules

### 1. Unified Trade Gate
- **File**: `backend/governance/css_unified_trade_gate.py`
- **Classification**: `CANONICAL`
- **Role**: Primary execution blocker and routing enforcer.

### 2. Regime Gate
- **File**: `engine/regime/regime_gate.py`
- **Classification**: `CANONICAL`
- **Role**: Operational mode enforcement.

### 3. Anti-Bleed Guard
- **File**: `backend/app/risk/anti_bleed_guard.py`
- **Classification**: `CANONICAL`
- **Role**: Profitability and cost-aware execution blocker.

### 4. Cross Asset Execution Orchestrator
- **File**: `backend/orchestration/cross_asset_execution_orchestrator.py`
- **Classification**: `CANONICAL`
- **Role**: Master execution router across all supported asset classes.

### 5. Legacy Mobile REST Endpoints
- **Classification**: `DEPRECATED` / `VIOLATION`
- **Role**: Removed to ensure single canonical execution path.

### 6. Legacy Risk Checkers
- **Classification**: `SHADOW` / `DEPRECATED`
- **Role**: Standalone risk scripts replaced by `anti_bleed_guard.py` and `cross_asset_execution_orchestrator.py`.
