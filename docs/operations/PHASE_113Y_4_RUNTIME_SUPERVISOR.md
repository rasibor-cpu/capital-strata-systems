# Phase 113Y-4 Runtime Supervisor

## Overview
The CSS Runtime Supervisor provides lightweight, observational monitoring for the CSS runtime engine. It exists purely as an operational control plane and does not influence trading logic, risk gates, or broker execution. 

## Responsibilities
- Track the lifecycle of the CSS runtime (START, STOP).
- Observe heartbeats emitted by the runtime loop.
- Record failure events and trigger state transitions (`DEGRADED`, `FAILED`).
- Provide restart recommendations (`should_restart()`) based on a safe maximum failure limit.
- Ensure state persistence to allow for external daemon monitoring and crash recovery.
- Dispatch System Alerts for observability without compromising runtime stability.

## Safety Invariants
1. **Observational Only:** The supervisor is decoupled from market logic.
2. **Fail-Open Alerting:** Alert emission failures are caught and swallowed; they will never crash the supervisor.
3. **Restricted Restarts:** The supervisor enforces a strict limit (`max_restart_limit=3`) before escalating to `FAILED` state to prevent infinite restart loops.

## State Representation
The supervisor state is written to `runtime/supervisor/css_runtime_supervisor_state.json` as a JSON object:
```json
{
  "supervisor_id": "uuid",
  "started_at": "ISO-8601",
  "stopped_at": null,
  "last_heartbeat_at": "ISO-8601",
  "failure_count": 0,
  "restart_count": 0,
  "last_failure": null,
  "status": "RUNNING",
  "max_restart_limit": 3
}
```

## Integration Next Steps
Subsequent phases will introduce external watchdogs (e.g., systemd or scheduled tasks) to monitor this JSON state file and orchestrate true OS-level restart procedures based on the supervisor's `should_restart()` assertions.
