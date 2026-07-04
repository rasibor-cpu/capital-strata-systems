# CSS Phase 153C - Broker Regression Startup Flow Fix

## Objective

Phase 153C hardens the startup workflow after the broker-selection refactor. The broker selection step must always occur after authentication/global mode selection and before broker execution arming.

## Root Cause

The startup refactor separated selected broker from broker execution arming, but the regression tests only verified that the selector function existed. They did not verify the actual top-level startup call order. This allowed the broker selection step to be skipped or bypassed without a strong regression signal.

## Canonical Startup Sequence

1. Authentication
2. Global Paper/Live selection
3. Broker selection
4. Broker-specific mode selection
5. Broker arming
6. Engine mode selection
7. Cycle mode selection
8. Runtime startup

Fail-closed security validation and broker-state persistence may occur after broker arming, but they must not skip broker selection or enable execution.

## Remediation

- Added a canonical startup sequence contract for broker startup tests.
- Added pure broker-choice helpers for invalid broker and disabled IBKR handling.
- Added explicit startup cancellation handling that returns NONE/PAPER with execution disabled.
- Added regression tests that inspect actual startup call ordering, not just function definitions.
- Preserved selected broker/mode when broker execution is disabled.

## Safety Boundary

Phase 153C does not enable live trading, does not arm broker execution, does not arm the Live Micro-Pilot, and does not bypass RBAC, Unified Trade Gate, Margin Gate, AntiBleedGuard, or Capital Governor.
