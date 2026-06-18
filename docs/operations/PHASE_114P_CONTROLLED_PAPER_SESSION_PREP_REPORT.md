# Phase 114P: Controlled Paper Session Prep Report

## Objective
Provide the formal readiness assessment and procedural execution commands prior to launching the first multi-day Controlled Paper Validation Session.

## 1. Readiness Checklist
- [x] **Branch Verified:** `css-evening-consolidation-2026-06-09` is active and clean.
- [x] **Test Suite Pass:** Full `pytest` integration and unit test suite explicitly passed.
- [x] **Dashboard Startup Command Validated:** Operators must use `python scripts/css_live_dashboard.py`.
- [x] **Paper/Practice Mode Only:** System strictly enforces `PAPER` mode selection via startup UI flow.
- [x] **Live Execution Disabled:** `.env.live` credentials are conditionally isolated; operator confirms selection of `PAPER` mode.
- [x] **Broker Mode Safe:** Default connection targets `api-fxpractice.oanda.com` or Coinbase Sandbox under `PAPER` directives.
- [x] **Evidence Locations Accessible:** Audit logs, `pnl_snapshots`, and JSON decision records map to proper local data directories.
- [x] **Shutdown Procedure Understood:** Graceful abort via `Ctrl+C` or UI signal intercepts trigger final state save.

## 2. Execution Commands
To instantiate the 48-72 hour paper validation session, the operator must execute the canonical startup sequence:

```bash
# 1. Initialize the GUI/CLI governance gate
python scripts/css_live_dashboard.py

# 2. Operator Interactive Flow
# -> Provide Authentication Token when prompted
# -> Select `PAPER` mode
```

## 3. Evidence to Collect
As defined in Phase 114C:
- **T=0:** Terminal log output of successful operator sign-on and environment variable binding.
- **T=24h/48h:** JSON dump of the running `pnl_snapshot`.
- **Throughout:** The `audit.log` capturing trade authorizations and broker rejections.
- **End:** Graceful shutdown trace confirming proper session archiving.

## 4. Stop Conditions
The session must be immediately aborted via standard OS signal interrupt if:
- The dashboard ceases to update real-time streams (stale feed > 15s).
- The memory profile exceeds threshold limits (e.g. system slowdown/OOM risk).
- Any trace of an unauthorized live API connection is detected.
- Any crash or unhandled python exception is thrown.

## 5. Final Recommendation
**READY FOR PAPER VALIDATION**

*Justification:* The codebase is confirmed green, and operational pathways correctly require manual operator sign-off into the `PAPER` execution context. No live connections will occur under this explicit procedure.
