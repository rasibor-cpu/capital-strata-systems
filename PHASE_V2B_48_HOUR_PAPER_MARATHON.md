# V2B 48-Hour Paper Marathon Runner

## Scope

Implemented a backend-only paper marathon runner that verifies V2A readiness, schedules repeated validation cycles, captures snapshots, maintains statistics, and produces a final certification report.

## Components

- `backend/validation/marathon_runner.py`
- `backend/validation/marathon_snapshot.py`
- `backend/validation/marathon_statistics.py`
- `backend/validation/marathon_certifier.py`

## Behavior

- Paper mode only
- No broker execution changes
- No UI modifications
- Supports checkpoint resume
- Stops on unhealthy runtime, disabled paper mode, recovery exhaustion, critical alerts, or heartbeat loss

## Output

The final certification report contains:

- `start time`
- `end time`
- `elapsed time`
- `cycles completed`
- `health summary`
- `alert summary`
- `recovery summary`
- `PnL summary`
- `decision summary`
- `replay summary`
- `GO`, `CONDITIONAL_GO`, or `NO_GO`