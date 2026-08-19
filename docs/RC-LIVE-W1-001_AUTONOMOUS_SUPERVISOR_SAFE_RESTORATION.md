# RC-LIVE-W1-001 — Autonomous Supervisor Safe Restoration

Canonical base: `css-v1.0.1-maintenance` @ `f70824f1e1deae34d24602597520411b88f7c311`.

This task restores the missing fail-closed autonomous supervisor module required by the existing maintenance test contract. The RC-LIVE implementation was used as a reference only; no RC-LIVE merge or cherry-pick was performed.

## Scope

Restored:

- `backend/runtime/autonomous_supervisor.py`

The supervisor returns only advisory runtime actions (`CONTINUE`, `REDUCE_EXPOSURE`, `PAUSE_STRATEGY`, `STOP_AUTONOMY`) and has no broker, order, credential, or execution-gate authority.

## Safety

No changes were made to Unified Trade Gate, AntiBleedGuard, Capital Governor, Margin Gate, RBAC, kill switches, broker adapters, live authorization TTL, live/paper defaults, order routing, order submission, MI-EXT, OANDA connectivity, or FX governor logic.

Safety review PASS:

- no broker, credential, order-submission, live-authority, execution-gate,
  governor, OANDA, MI-EXT, or FX capability introduced

## Validation

Runtime validation has been executed. This task is independently review-ready and authorized to land via draft PR #58.

Exact results:

- `python3 -m py_compile backend/runtime/autonomous_supervisor.py` — PASS
- `python3 -m pytest tests/test_autonomous_supervisor.py -v` — 5 passed / 0 failed
- no other Python runtime importers found
- `git diff --check` — PASS
- working tree clean
- safety review PASS:
  no broker, credential, order-submission, live-authority, execution-gate,
  governor, OANDA, MI-EXT, or FX capability introduced
