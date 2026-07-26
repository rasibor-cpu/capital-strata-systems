# Phase 183B-D Deterministic State Isolation and Hydration Recovery

Status: implementation complete, not certified for production.

This phase reduces full-suite-only contamination and dashboard/mobile rendering regressions without changing runtime-mode authority, broker readiness, OANDA quarantine, firewall, certification, or live-trading semantics.

## Scope

- Test isolation for authentication observability, dashboard broker globals, runtime snapshot clock drift, and missing-credential checks.
- Fail-closed account hydration for dashboard and mobile payloads.
- Frontend default and websocket delta determinism.
- Limited fixture/path isolation where failures were caused by local state leakage.

## Explicit Exclusions

- Runtime authority reconciliation is not changed in this phase.
- OANDA quarantine and firewall precedence are not changed in this phase.
- Broker readiness vocabulary is not changed in this phase.
- Certification conclusions are not changed in this phase.
- Production persistence semantics are not redesigned in this phase.
- OV-002 Attempt 3 is not started.
- Live trading remains unauthorized.

## Test Isolation Policy

Tests must not rely on machine-local runtime state, prompt for authentication, or inherit process globals from earlier tests. Auth observability tests use temporary session and audit files, direct object patching for the imported auth module, and per-test `AuthMetrics` reset. Legacy script tests that replace `dashboard.auth.css_sign_on` are treated as contamination sources; auth tests repair the import path before importing the canonical module.

Dashboard tests that mutate `scripts.css_live_dashboard` broker globals must restore those values after each test. Tests requiring a fresh validation sequence must reset `PCNRASS_VALIDATION_SEQUENCE` explicitly.

Runtime freshness tests must generate live heartbeat timestamps at test execution time, not collection time. Collection-time timestamps can become stale during the full suite and must not be used as proof of live runtime health.

## Environment Isolation Policy

Tests that validate missing broker credentials must prevent local credential profiles and dotenv state from entering the assertion path. Missing credentials remain fail-closed, no credential values are printed, and no broker network connection is attempted.

Environment isolation remains narrow: tests that intentionally validate environment variables continue to set those variables locally.

## Account Hydration Semantics

Dashboard account state now distinguishes:

- known numeric zero
- known positive or negative number
- unavailable
- invalid
- stale or not tested where supplied by callers

Unavailable, missing, malformed, empty, non-finite, and sentinel account values are not displayed as factual financial zero. Numeric fallbacks are used only for internal calculations that require numbers, while display payloads retain availability fields and unavailable values.

UI payloads must not crash on unavailable account fields. Execution posture remains blocked and advisory-only.

## Frontend Default Policy

Currency is not fabricated. If no canonical account currency is available, frontend payloads report `UNAVAILABLE` with unavailable availability/source metadata. Legacy implicit `USD` defaulting is prohibited unless a canonical source supplies it.

## Websocket Delta Policy

Equivalent source snapshots must not emit broker deltas only because volatile broker metadata changed. Broker `correlation_id` and `received_at` are excluded from broker delta comparison. Meaningful broker status, source, freshness, or health changes still emit broker deltas.

## Global Provider Reset Policy

Mutable dashboard globals, auth module replacements, imported auth ledger bindings, and runtime freshness timestamps are reset or generated per test where they previously leaked across the full suite. Local runtime artifacts remain non-authoritative for focused tests unless explicitly injected through temporary paths.

## Verification Summary

- Focused Phase 183B-D suite: 51 passed.
- Collection: 3277 collected.
- First full suite after fixes: 26 failed, 3246 passed, 5 skipped, 2 warnings.
- Repeated full suite: 26 failed, 3246 passed, 5 skipped, 2 warnings.

## Remaining Failure Clusters

- Runtime-mode authority and legacy paper/live expectations.
- OANDA quarantine/firewall precedence.
- Broker readiness vocabulary and dashboard status mapping.
- Trade outcome persistence path isolation.
- Dashboard subtab/mobile manifest contract drift.
- OV001 shutdown evidence scoring.
- Institutional reports and branding contract mismatches.

## Safety Posture

The phase preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

No broker authentication, live execution, deployment, runtime restart, certification claim, or OV-002 Attempt 3 action is authorized by this phase.
