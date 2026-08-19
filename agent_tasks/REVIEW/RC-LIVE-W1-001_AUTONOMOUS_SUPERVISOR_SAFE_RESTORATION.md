---
id: RC-LIVE-W1-001
status: REVIEW
priority: 120
risk: LOW
owner: ChatGPT GitHub connector
base_branch: css-v1.0.1-maintenance
starting_head: f70824f1e1deae34d24602597520411b88f7c311
claimed_branch: css-rclive-w1-autonomous-supervisor
commit_authority: FEATURE_BRANCH
push_authority: FEATURE_BRANCH
pr_authority: DRAFT_TO_MAINTENANCE
live_trading_authority: NONE
---

# RC-LIVE-W1-001 — Autonomous Supervisor Safe Restoration

## Objective

Restore the missing `backend/runtime/autonomous_supervisor.py` required by the canonical maintenance test contract, using the RC-LIVE implementation as a reference only.

## Scope

- Restore only the fail-closed autonomous supervisor module.
- Preserve advisory/non-executing behavior.
- Do not modify live authority, broker adapters, execution gates, capital controls, RBAC, kill switches, mobile TTL, OANDA connectivity, MI-EXT, FX governor logic, or live/paper defaults.

## Evidence

Canonical maintenance at task start: `f70824f1e1deae34d24602597520411b88f7c311`.

Existing canonical test contract: `tests/test_autonomous_supervisor.py` imports `AutonomousSupervisor` and `AutonomousSupervisorError` and expects CONTINUE, REDUCE_EXPOSURE, PAUSE_STRATEGY, STOP_AUTONOMY, and fail-closed invalid input behavior.

The implementation restored on this branch matches that narrow contract and retains safety-stop behavior for critical alerts, exhausted recovery, stale heartbeat, and drawdown limits.

## Validation status

Static contract inspection complete. Runtime/pytest execution still requires an execution environment and independent validation before merge.

## Safety

- live trading authority: NONE
- broker credential access: NONE
- order submission: NONE
- execution-gate mutation: NONE
- capital-governor mutation: NONE
- runtime deployment: NONE

## Review gate

Do not merge until `tests/test_autonomous_supervisor.py` and compile checks are executed successfully in a repository runtime and the branch diff is independently reviewed.
