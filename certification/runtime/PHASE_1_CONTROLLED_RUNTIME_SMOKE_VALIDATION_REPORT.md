# Phase 1 Controlled Runtime Smoke Validation Report

Date: 2026-06-15 12:22:01 -04:00

Branch: `css-evening-consolidation-2026-06-09`

Commit: `631dcf17639acd7a8e501334c320c65b27deee14`

Scope: Stage 3B controlled runtime smoke validation for CSS V1 certification evidence.

Mode restriction: PAPER / DEMO only. No live broker order placement was performed. No runtime code, trading logic, broker logic, risk policy, dashboard behavior, credentials, thresholds, or execution behavior were changed.

## Verification Before Start

`git remote -v`

```text
origin  https://github.com/rasibor-cpu/capital-strata-systems.git (fetch)
origin  https://github.com/rasibor-cpu/capital-strata-systems.git (push)
```

`git branch --show-current`

```text
css-evening-consolidation-2026-06-09
```

`git rev-parse HEAD`

```text
631dcf17639acd7a8e501334c320c65b27deee14
```

`git status`

```text
On branch css-evening-consolidation-2026-06-09
Your branch is up to date with 'origin/css-evening-consolidation-2026-06-09'.

nothing to commit, working tree clean
warning: could not open directory '.pytest_cache/': Permission denied
```

## Runtime Validation Report

### 1. Startup Sequence

Command:

```text
.\.venv\Scripts\python.exe -m dashboard.runtime.runtime_smoke_test
```

Result:

```text
CSS runtime smoke test PASSED
Validated: imports, builders, contracts, renderers, bootstrap, demo runner, live payload adapter
```

Assessment: PASS. Runtime imports, state builders, render contracts, renderers, bootstrap, demo runner, and live payload adapter initialized successfully under controlled PAPER/DEMO inputs.

### 2. Authentication Sequence

Controlled in-memory auth sequence:

```text
AUTH_SEQUENCE PASSED
login_ok= True
username= admin
roles= ['TRADER']
token_returned=<hidden>
session_validated= True
token_revoked= True
```

Assessment: PASS. Authentication was validated with a temporary process-only test credential value, in-memory OTP handling, hidden token output, session validation, and revocation. No real credential value or session token was printed.

### 3. Broker Selection Sequence

Dashboard startup evidence rendered:

```text
Broker:                  DEMO
Mode:                    paper
Selected Broker:         DEMO
Broker Mode:             paper
Connected:               NO
Live Trading Enabled:    NO
Readiness Status:        BROKER_DEGRADED
Readiness Reasons:       broker_not_connected
```

Assessment: PASS WITH OBSERVATION. Broker selection resolved to DEMO/PAPER. The degraded readiness status is expected for this controlled non-live smoke because no live broker connection was requested.

### 4. PAPER Mode Confirmation

Dashboard startup evidence rendered:

```text
Runtime Mode:   paper
Broker Mode:             paper
Live Trading Enabled:    NO
```

Execution disposition evidence:

```text
execution_disposition_execute_trade= False
broker_mode=paper
```

Assessment: PASS. Runtime and broker mode were paper-only, and the orchestrator disposition did not enable execution.

### 5. Dashboard Startup

Command:

```text
.\.venv\Scripts\python.exe -m dashboard.runtime.demo_runtime_runner
```

Rendered sections confirmed:

```text
CAPITAL STRATA SYSTEMS DASHBOARD
ACCOUNT SUMMARY
PnL SUMMARY
MARKET INTELLIGENCE
GOVERNANCE STATE
RISK SUMMARY
EXECUTION SUMMARY
BROKER STATE
RUNTIME DIAGNOSTICS
```

Assessment: PASS. Dashboard runtime bootstrap rendered the expected operational panels from controlled DEMO/PAPER payloads.

### 6. Canonical Trade-Gate Evaluation Path

Controlled candidate:

```text
{'symbol': 'BTC-USD', 'asset_class': 'crypto', 'expected_value': 1.0, 'cost': 0.0, 'probability': 1.0, 'engine_mode': 'SAFE'}
```

Decision trace:

```text
DECISION_TRACE PASSED
orchestration=TradeDecisionOrchestrator.evaluate_trade
canonical_gate= CSSUnifiedTradeGate
governance_approved= True
governance_reason= approved: prob=1.000 >= 0.650, cost=0.0000 < ev=1.0000
execution_disposition_execute_trade= False
broker_mode=paper
session_id_present= True
```

Assessment: PASS. Runtime governance decision fields originated from `CSSUnifiedTradeGate` through `TradeDecisionOrchestrator.evaluate_trade`. The final execution disposition remained `False`.

### 7. Runtime Governance Decision Trace

Required path:

```text
candidate
-> TradeDecisionOrchestrator.evaluate_trade
-> CSSUnifiedTradeGate
-> governance decision
-> execution disposition
```

Observed path:

```text
candidate:
  symbol: BTC-USD
  asset_class: crypto
  expected_value: 1.0
  cost: 0.0
  probability: 1.0
  engine_mode: SAFE

orchestration:
  TradeDecisionOrchestrator.evaluate_trade

canonical governance source:
  CSSUnifiedTradeGate

governance decision:
  approved=True
  reason="approved: prob=1.000 >= 0.650, cost=0.0000 < ev=1.0000"

execution disposition:
  execute_trade=False
  broker_mode=paper
```

Assessment: PASS. The decision trace proves canonical gate sourcing while preserving non-execution behavior in the runtime orchestrator.

### 8. Runtime Warning Inventory

| Source | Severity | Warning / Observation | Action Required |
|---|---|---|---|
| Dashboard runtime diagnostics | None | `Warnings: NONE` | None |
| Dashboard hydration diagnostics | None | `Hydration Gaps: NONE`; `Builder Failures: NONE`; `Governance Alerts: NONE` | None |
| Broker readiness display | Observation | DEMO broker rendered `BROKER_DEGRADED` because no live broker connection was requested | None for PAPER smoke; expected non-live condition |
| Git status | Observation | `.pytest_cache/` permission warning during status checks | None for runtime certification; unrelated to runtime behavior |
| Initial sandbox execution | Observation | Repo venv base interpreter required approved escalation from sandbox | None for runtime behavior; validation succeeded after approved execution |
| Initial auth attempt | Observation | Normal OTP email path failed because email destination was not configured | None for runtime behavior; corrected with headless in-memory auth mode |
| Initial temp DB attempt | Observation | Temp runtime DB needed migrations resolved from repo path | None for runtime behavior; corrected by setting process-local temp DB path |

Assessment: PASS WITH OBSERVATIONS. No runtime dashboard warnings, hydration gaps, builder failures, or governance alerts were observed. Setup observations did not alter runtime code or live execution behavior.

### 9. Shutdown Sequence

Shutdown evidence:

```text
runtime_smoke_test exit code: 0
demo_runtime_runner exit code: 0
auth validation exit code: 0
decision trace exit code: 0
```

Assessment: PASS. All controlled validation commands completed and returned to shell without leaving a required foreground service running. The decision-trace runtime used a temporary SQLite path outside the repository for local persistence side effects.

## Runtime Decision Path

```text
candidate
-> orchestration
-> CSSUnifiedTradeGate
-> governance decision
-> execution disposition
```

Concrete evidence:

```text
candidate={'symbol':'BTC-USD','asset_class':'crypto','expected_value':1.0,'cost':0.0,'probability':1.0,'engine_mode':'SAFE'}
orchestration=TradeDecisionOrchestrator.evaluate_trade
canonical_gate=CSSUnifiedTradeGate
governance_approved=True
execution_disposition_execute_trade=False
broker_mode=paper
```

## Certification Recommendation

PASS WITH OBSERVATIONS

Rationale:

- Runtime smoke validation passed.
- Dashboard startup rendered expected panels.
- Authentication sequence passed with hidden token output and revocation.
- Broker selection resolved to DEMO/PAPER.
- PAPER mode and live-disabled state were confirmed.
- Runtime governance decision source was `CSSUnifiedTradeGate`.
- Final execution disposition remained non-executing.
- No dashboard runtime warnings, hydration gaps, builder failures, or governance alerts were observed.
- Observations are limited to expected non-live broker readiness and controlled setup corrections, not certification-blocking runtime behavior.

