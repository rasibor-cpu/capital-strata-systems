# Mission Control Disaster Recovery

## Purpose

Mission Control is a read-only dashboard layer. Recovery focuses on restoring
visibility without changing trading authority.

## Recovery Checks

1. Verify the dashboard host is reachable.
2. Verify runtime artifacts are present and valid JSON.
3. Verify runtime heartbeat freshness.
4. Verify source registry diagnostics.
5. Verify final certification status.
6. Verify safety flags remain blocked/read-only.

## Corrupt Or Missing Runtime Artifacts

Mission Control must fall back to offline/unavailable state when artifacts are
missing or corrupt. Do not treat cached or partial state as current runtime
evidence.

## Rollback Planning

The rollback planner lists eligible targets from audit/change history evidence.
It does not perform rollback.
