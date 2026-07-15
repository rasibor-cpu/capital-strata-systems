# Phase 166D - Live Environment Contamination Elimination

## Purpose

Phase 166D removes the remaining live startup blocker caused by the paper-only variable `COINBASE_TEST_ORDER_USD` appearing in a LIVE process environment.

This phase is read-only and fail-closed. It does not enable execution, submit orders, change credentials, modify API keys, alter secrets, or change account configuration.

## Root Cause

`COINBASE_TEST_ORDER_USD` is defined only in `.env.practice`. It is a paper/practice test-order notional used by legacy dashboard simulation code and contamination regression tests.

The contamination entered LIVE startup because these wrappers loaded `.env.practice` unconditionally before broker mode was fully resolved:

- `scripts/css_live_dashboard.py`
- `launcher/css_runtime_launcher.py`
- `launcher/css_mobile_launcher.py`

With `override=False`, `.env.practice` did not overwrite existing values, but it still injected missing paper-only variables into the inherited process environment. The canonical broker environment registry then correctly rejected `COINBASE_TEST_ORDER_USD` in LIVE mode.

## Variable Classification

| Variable | Source file | Purpose | Read by | Runtime mode | Used | Deprecated | Compatibility | Required | Safe to remove from LIVE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `COINBASE_TEST_ORDER_USD` | `.env.practice` line 2 | Paper/practice test-order notional | Legacy dashboard simulation path and tests | Paper/practice only | Yes, paper compatibility | No | Yes | No for paper tests | Yes |
| `COINBASE_TEST_ORDER_USD` | `backend/runtime/canonical_broker_state_registry.py` | Classify as TEST contamination in LIVE | Canonical environment diagnostics | LIVE validation | Yes | No | Diagnostic compatibility | Yes | No, diagnostic registry remains |
| `COINBASE_TEST_ORDER_USD` | `scripts/css_live_dashboard.py` | Paper-only simulated test order sizing | Dashboard simulation path | Paper/practice only | Yes | Legacy compatibility | Yes | No for LIVE | Yes |
| `COINBASE_TEST_ORDER_USD` | Tests | Regression evidence | Pytest only | Test | Yes | No | Test fixture | Yes | Not applicable |
| `COINBASE_TEST_ORDER_USD` | Historical review folders/logs | Archived evidence | Not runtime | None | No | Yes | Historical | No | Not runtime |

## Environment Load Order

Before Phase 166D:

1. Process environment inherited from shell, Windows, PowerShell, service manager, or parent launcher.
2. Runtime wrapper loaded `.env`.
3. Runtime wrapper loaded `.env.practice` with `override=False`.
4. Credential loaders sometimes loaded `.env.practice` again only for non-live modes.
5. Canonical environment validation rejected paper/test keys in live mode.

After Phase 166D:

1. Process environment is inherited.
2. Shared loader loads `.env`.
3. Shared loader skips `.env.practice` when mode is LIVE or unknown at early startup.
4. Shared loader removes paper-only Coinbase keys from LIVE/unknown startup inheritance.
5. Mode-specific credential loaders may still load `.env.practice` for non-live modes only.
6. Canonical validation sees no `COINBASE_TEST_ORDER_USD` in LIVE unless an explicit caller passes it, in which case validation still fails closed.

## Live Startup Lifecycle

`COINBASE_TEST_ORDER_USD` lifecycle after remediation:

- absent from clean LIVE startup before dotenv loading
- not loaded from `.env.practice` during LIVE/unknown wrapper startup
- removed if inherited from process environment before canonical validation
- still rejected if explicitly supplied to live validation APIs
- retained for paper/practice paths where it is paper-only metadata

Values are never printed by the loader.

## Remediation

Added `backend/runtime/live_environment_loader.py`:

- loads `.env`
- skips `.env.practice` for LIVE or unknown early startup
- loads `.env.practice` only for explicit non-live modes
- removes `COINBASE_TEST_ORDER_USD` from live inherited environments
- keeps safety flags advisory and fail-closed

Updated dashboard and launcher wrappers to use this loader instead of unconditional `.env.practice` loading.

## Safety

Preserved:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `paper_only=true`
- `advisory_only=true`

No broker execution, credential, permission, account, or deployment behavior was expanded.
