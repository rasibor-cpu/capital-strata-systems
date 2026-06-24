# Phase T3 Options and Futures Completion

## Scope
- Complete the options and futures lifecycle adapters so they expose the same canonical open/close normalization and warehouse persistence contract already used by FX and crypto.
- Preserve the existing dry-run execution semantics and avoid changes to broker authentication, live execution permissions, RBAC, mobile UI, or launcher UI.

## Implemented
- Added options lifecycle adapter with canonical open/close payload construction, normalization, and paper execution integration.
- Added futures lifecycle adapter with canonical open/close payload construction, normalization, and paper execution integration.
- Added regression tests for options and futures open/close lifecycle, paper mode, warehouse persistence, analytics compatibility, duplicate prevention, and fail-closed behavior.

## Validation
- python -m pytest tests/test_options_lifecycle.py tests/test_futures_lifecycle.py tests/test_canonical_trade_lifecycle.py tests/test_asset_lifecycle_integration.py -v
