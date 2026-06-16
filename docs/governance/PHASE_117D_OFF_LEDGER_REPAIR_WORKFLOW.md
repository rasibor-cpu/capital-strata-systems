# PHASE 117D - OFF-LEDGER REPAIR WORKFLOW

## Overview
Capital Strata Systems (CSS) enforces strict parity between the Local Ledger (`mtm_engine`) and the executing Broker (e.g., OANDA). Any divergence detected during startup or continuous polling triggers an immediate safety response. To protect institutional capital from runaway automated trading algorithms, CSS does **not** employ automated position-flattening. Instead, all detected anomalies are routed into an Off-Ledger Repair Workflow requiring manual, human-driven intervention.

## Divergence Categories
Divergences detected by the reconciliation engine are classified into exactly three categories:

1. **ORPHAN_BROKER_POSITION**: A live trade exists on the broker that is missing from the local ledger.
2. **GHOST_LOCAL_POSITION**: The local ledger believes it holds a live trade, but the broker has no record of it.
3. **BROKER_POSITION_MISMATCH**: Both environments track the trade, but critical fields (e.g., unit quantities) are mismatched.

## Defensive Posture & Record Creation
When parity is lost, the `RepairEngine` guarantees the following sequential safety cascade:

1. The exact divergence event is packaged into an immutable `RepairRecord` labeled with a unique `REP-` ID.
2. The session immediately invokes `lock_session("RECONCILIATION_DIVERGENCE")`.
3. Defensive Mode activates globally, forcefully rejecting all new live capital deployment attempts until the lock is lifted.
4. The dashboard prominently alerts operators to the active anomalies.

## Manual Resolution Protocol
Operators must investigate the root cause via broker statements or latency logs. Once isolated, the repair must be categorized according to one of the following resolution pathways:

- **OFF_LEDGER_CLOSE**: The position was closed directly via the broker's web UI.
- **OFF_LEDGER_LIQUIDATION**: A margin/stop liquidation occurred outside of the CSS engine loop.
- **MANUAL_LEDGER_SYNC**: The local ledger was manually edited to ingest a missing valid position.

To resolve a record and clear the dashboard warnings, execute the following internal resolution command mapping:
```python
repair_engine.resolve_record(record_id, "OFF_LEDGER_CLOSE", "Operator closed via web portal.")
```

Once all records reflect `status: REPAIRED`, an administrator may safely lift the `lock_session` flag to resume live operations.
