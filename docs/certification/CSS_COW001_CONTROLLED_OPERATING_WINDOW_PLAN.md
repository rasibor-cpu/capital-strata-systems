# CSS-COW-001 — Controlled Operating Window

## Status

READY_FOR_OPERATOR_RUN

## Objective

Run the certified CSS integration lineage unchanged for a minimum continuous 24-hour controlled operating window in paper/advisory mode while observing current market-data flow and preserving complete operational evidence.

This assignment is an operational certification run, not a development sprint.

## Certified starting point

- Base certification commit: `d416070d852c2a505a4d63fdb571e5f9cacc7b2c`
- Integration branch source: `css-qro004x-integration-2026-09-13`
- COW branch: `css-cow001-controlled-operating-window`
- Full integrated regression already certified: 1874 passed
- Live broker execution remains disabled

## Required operating state

The window may start only if all of the following are true:

- working tree is clean;
- branch is `css-cow001-controlled-operating-window`;
- no uncommitted runtime/code changes exist;
- system mode is PAPER / advisory only;
- `execution_allowed = false`;
- `live_trading_blocked = true`;
- `broker_execution_armed = false`;
- `advisory_only = true`;
- no credential/token material is written to evidence;
- market-data observations are current and are not being represented as live broker-account authorization;
- Questrade live account authorization remains treated as externally blocked unless separately resolved.

## Minimum duration

- Required: 24 continuous hours.
- Preferred extension: continue to 48 hours if the first 24 hours are clean and the operator is available.
- A fatal crash, hard stall, unauthorized execution path, state corruption, or critical risk-gate breach invalidates the window and resets the clock.

## Evidence cadence

### T+0

Capture:

- UTC/local start timestamp;
- branch and exact HEAD;
- `git status --short`;
- Python version;
- supervisor/runtime process state;
- paper/advisory safety flags;
- current market-data freshness/source metadata available from the runtime;
- initial hashes of runtime/evidence files.

### Hourly

Capture:

- supervisor PID and child PID;
- supervisor status;
- restart count and unexpected restart count;
- last exit code;
- last-observed timestamp;
- runtime process presence;
- market-data freshness/source evidence if available;
- PnL/session analyzer output;
- hashes of key state files;
- process CPU and memory footprint;
- read-only runtime-health projection;
- read-only broker-continuity projection, including freshness and fail-closed safety flags;
- any warnings/errors.

### Every 6 hours

Operator visual check:

- dashboard remains responsive;
- displayed mode remains PAPER / advisory;
- displayed positions/PnL align with canonical persisted state;
- market data continues updating;
- no hidden live execution state appears;
- no security or credential leakage appears in UI/logs.

### T+24

Capture:

- final hourly sample;
- final `css_session_analyzer.py` output;
- final supervisor state;
- final hashes;
- final process/runtime status;
- clean shutdown evidence;
- incident summary;
- PASS / FAIL / PASS_WITH_OBSERVATIONS disposition.

## Pass criteria

COW-001 is PASS only if all mandatory criteria hold:

1. 24 continuous hours complete.
2. No fatal crash.
3. No hard stall requiring kill/restart.
4. No unauthorized live order attempt.
5. No transfer/withdrawal/deposit/funding/money movement path activated.
6. Risk/governance gates remain enforced.
7. Runtime state remains readable and non-corrupt.
8. Supervisor telemetry remains coherent.
9. Any restart is fully explained, bounded, and does not violate safety invariants.
10. Market-data freshness remains observable and stale states are labeled explicitly.
11. Aggregate runtime working-set growth from first to final captured sample is <=15%.
12. Every captured broker-continuity projection preserves execution_allowed=false, live_trading_blocked=true, broker_execution_armed=false, and advisory_only=true.
13. No credential/token leakage in retained evidence.
14. Final shutdown is graceful.

## Failure criteria

Immediate FAIL if any of the following occurs:

- live broker order submission;
- live execution flag becomes enabled;
- runtime corruption;
- supervisor enters unrecoverable manual-intervention state;
- silent stale market-data state represented as current;
- critical risk-gate bypass;
- credential/token leak;
- hard crash/freeze requiring forced termination.

## Incident classification

- LOW — cosmetic or non-safety issue; continue and log.
- HIGH — stale data, repeated restart, PnL mismatch, or degraded continuity; pause and review.
- CRITICAL — unauthorized execution, risk bypass, corruption, or secret exposure; stop immediately and invalidate the window.

## Operator commands

From the COW branch:

```powershell
Set-Location 'C:\rasib\source\capital-strata-systems-QRO001'
git fetch origin
git switch css-cow001-controlled-operating-window
git pull --ff-only
powershell -ExecutionPolicy Bypass -File scripts\ops\cow001_preflight.ps1
```

After a clean preflight, start the existing certified runtime using the normal runtime-supervisor launch path. Do not alter code/config to make the run pass.

Use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\ops\cow001_capture_sample.ps1 -Label T00
```

Then repeat hourly with labels `T01` through `T24`.

At completion:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\ops\cow001_finalize.ps1
```

## Non-authorizations

COW-001 does not authorize:

- live trading;
- broker mutation;
- client funds;
- transfer/withdrawal/deposit/funding;
- fee collection;
- bypass of Questrade external authorization controls.

The purpose is to observe the already-certified system under sustained controlled conditions.
