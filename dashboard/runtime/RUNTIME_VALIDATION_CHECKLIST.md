# CSS Runtime Validation Checklist

Status: PCNRASS validation checklist for dashboard runtime architecture.

PCNRASS means: Please Confirm No Regression And Stable State.

Use this checklist before and after each dashboard runtime milestone.

## 1. Repository Baseline

- Confirm current branch:

```powershell
git branch --show-current
```

- Confirm working tree state:

```powershell
git status --short
```

- Confirm latest runtime milestones:

```powershell
git log --oneline -10
```

- Expected tolerated local change:

```text
 m CSS-CLAUDE
```

Do not stage, revert, or modify `CSS-CLAUDE` unless explicitly requested.

## 2. Compile Checks

Compile any changed Python file before running it:

```powershell
.\.venv\Scripts\python.exe -m py_compile <changed_file.py>
```

For runtime architecture changes, compile the core runtime path:

```powershell
.\.venv\Scripts\python.exe -m py_compile dashboard\runtime\runtime_bootstrap.py dashboard\runtime\dashboard_hydration_coordinator.py dashboard\runtime\dashboard_state_factory.py dashboard\runtime\dashboard_renderer.py dashboard\runtime\demo_runtime_runner.py
```

If renderers, contracts, builders, or summaries changed, compile those files too.

## 3. Runtime Demo Validation

Run the isolated runtime demo from repo root:

```powershell
.\.venv\Scripts\python.exe -m dashboard.runtime.demo_runtime_runner
```

Expected sections:

- Account Summary
- PnL Summary
- Market Intelligence
- Governance State
- Risk Summary
- Execution Summary
- Broker State
- Runtime Diagnostics

Expected demo signals:

- Broker: `DEMO`
- Runtime Mode: `paper`
- Engine Mode: `SAFE`
- Unrealized PnL: `27.50`
- Total Exposure: `4,362.50`
- Market Trend State: `UPTREND`
- Governance Enabled: `YES`
- Risk State: `NORMAL`
- Execution State: `READY`

## 4. Hydration Validation

Verify payload flow remains:

```text
payloads
-> DashboardHydrationCoordinator
-> DashboardStateFactory
-> DashboardState
-> DashboardRenderer
-> terminal output
```

Checklist:

- Account payload hydrates cash, equity, buying power, margin, currency.
- Broker payload or account fallback hydrates selected broker and mode.
- Positions payload hydrates open count, exposure, winners, losers, asset PnL.
- Market payload hydrates `state.global_market_state`.
- Governance payload hydrates `state.governance_state`.
- Risk payload hydrates `state.last_scan_results["risk_summary"]`.
- Execution payload hydrates `state.last_scan_results["execution_summary"]`.
- Diagnostics payload is retained in `state.dashboard_messages`.

## 5. Renderer Validation

Renderer rules:

- Renderers consume render contracts only.
- Renderers do not access engines.
- Renderers do not access brokers.
- Renderers do not calculate business truth.
- Renderers do not mutate `DashboardState`.

Current pure renderers:

- `AccountRenderer`
- `PnLRenderer`
- `MarketRenderer`
- `GovernanceRenderer`
- `RiskRenderer`
- `ExecutionRenderer`
- `BrokerRenderer`
- `DiagnosticsRenderer`

## 6. Regression Checks

Do not regress:

- `scripts/css_live_dashboard.py` login/session flow.
- Global broker mode selection.
- Broker execution arming.
- Engine mode selection.
- Paper-only safe operation.
- Existing account and PnL visibility.
- Existing governance/session visibility.
- Runtime demo output.

Do not aggressively rewrite `scripts/css_live_dashboard.py`.

## 7. Rollback Checks

Before commit:

- Confirm only intended files are staged.
- Confirm unrelated `CSS-CLAUDE` status is untouched.
- Confirm runtime demo passes.
- Confirm no production dashboard rewrite was introduced.

Commands:

```powershell
git diff --cached --stat
git status --short
```

## 8. Commit And Push

Stable commit format:

```powershell
git commit -m "PCNRASS <clear milestone>"
git push origin main
```

After push:

```powershell
git status -sb
```

Expected:

```text
## main...origin/main
 m CSS-CLAUDE
```

## 9. Failure Handling

If compile fails:

- Stop.
- Fix syntax/import issue.
- Recompile.

If demo fails:

- Stop.
- Compare against the last passing milestone.
- Do not continue to live dashboard work.

If unrelated project-wide tests fail:

- Record the failure.
- Determine whether failure predates the runtime milestone.
- Do not mix unrelated fixes into the runtime milestone.
