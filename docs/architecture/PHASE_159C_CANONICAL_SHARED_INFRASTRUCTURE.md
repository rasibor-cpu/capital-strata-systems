# Phase 159C – Canonical Shared Infrastructure Governance

## Purpose & Summary

Phase 159C introduces the **Canonical Shared Infrastructure** package for the Capital Strata Systems (CSS) codebase, consolidating duplicated numeric normalizations, status strings, metrics thresholds, and payload construction builders into a centralized `backend/common` module.

This engineering-quality milestone removes redundancy while maintaining 100% functional, signature, and output compatibility with all preceding phases (157A/B/C, 158A, and 159A/B).

---

## Subsystem Details

### 1. Status Types (`backend/common/status_types.py`)
Centralizes primary status strings:
- Metric Alerts: `GREEN`, `AMBER`, `RED`, `UNKNOWN`
- Lifecycle States: `NOT_READY`, `READY`
- Validation Gates: `PASS`, `FAIL`

### 2. Global Constants (`backend/common/constants.py`)
Defines shared limits and bounds:
- `CONFIDENCE_WARNING_THRESHOLD = 70.0`
- `CONFIDENCE_CRITICAL_THRESHOLD = 60.0`
- `PORTFOLIO_DRAWDOWN_WARNING_THRESHOLD = 8.0`
- `PORTFOLIO_CONCENTRATION_WARNING_THRESHOLD = 50.0`

### 3. Numeric Utilities (`backend/common/numeric_utils.py`)
Consolidates standard arithmetic coercion helpers:
- `safe_float()`: Safe conversion to floating-point number, falling back to a default value on parsing errors or non-finite outputs.
- `safe_int()`: Safe conversion to integer, routing through float checks to support values like `"42.0"`.
- `safe_bool()`: Flexible parser mapping strings (`"true"`, `"yes"`, `"on"`, `"1"`, `"ok"`) to boolean states.
- `clamp()`: Restricts a numeric value between a specified minimum and maximum bound.
- `normalize_percentage()`: Utility clamping inputs to `[0.0, 100.0]`.

### 4. Advisory Payload Builder (`backend/common/advisory_payload.py`)
Defines the unified `AdvisoryPayloadBuilder` class. 
This builder introduces defense-in-depth safety checks. It overrides payload input parameters to force safety bounds on execution and trading controls:
- `advisory_only` is locked to `True`.
- `execution_allowed` is locked to `False`.
- `live_trading_blocked` is locked to `True` (if present).
- `broker_execution_armed` is locked to `False` (if present).
