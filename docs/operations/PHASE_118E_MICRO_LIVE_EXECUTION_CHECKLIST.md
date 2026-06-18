# Phase 118E: Micro-Live Execution Checklist

This checklist must be rigorously followed by the operator during the execution of the Phase 118E Micro-Live Pilot. Any deviations require immediate abortion of the session.

## PRE-LAUNCH
- [ ] Verify target branch is exactly `css-evening-consolidation-2026-06-09`.
- [ ] Verify `python -m pytest` passes 100% locally.
- [ ] Verify working tree is clean.
- [ ] Isolate `.env` file containing explicit OANDA Live Credentials.
- [ ] Verify `OANDA_ENV=live` is set.
- [ ] Verify *no* practice or test variables exist in the shell environment.
- [ ] Log into the OANDA Web Portal and verify existing account equity is ≤ $1,000 USD and 0 open positions exist.

## LAUNCH
- [ ] Execute `python scripts/css_live_dashboard.py`.
- [ ] Validate `=== SECURITY STATUS ===` prints ALL `YES` explicitly.
- [ ] Acknowledge the Live Trading Risk Disclaimer on screen.
- [ ] Validate that Startup Reconciliation successfully passes with no immediate divergences.
- [ ] Validate Broker Health establishes as `GREEN`.

## DURING SESSION
- [ ] Monitor Continuous Reconciliation Heartbeat logs for any anomaly.
- [ ] Monitor for `[RATE LIMIT]` or `[DEGRADED]` health state warnings.
- [ ] Observe Slippage metrics (`expected_price` vs `actual_fill_price`) upon execution of any strategy order.
- [ ] Ensure open positions never exceed 3.
- [ ] Maintain constant physical access to the terminal to initiate manual repair if the session locks.

## POST-SESSION
- [ ] Manually halt the CSS Live Dashboard gracefully.
- [ ] Export session logs.
- [ ] Compare local `TradeLedger` records against the OANDA Web Portal broker statement.
- [ ] Calculate maximum drawdown experienced.
- [ ] Document any slippage violations or latency spikes.

## ABORT PROCEDURE
If an Abort Condition is met (e.g., `GHOST_LOCAL_POSITION` detected or Max Daily Loss > $20):
1. **HALT SCRIPT**: Issue `CTRL+C` immediately to kill the CSS engine.
2. **BROKER FLATTEN**: Log into the OANDA Web Portal and immediately "Close All Positions".
3. **LOG PRESERVATION**: Copy `css_live_dashboard.log` and all console output before closing the terminal.
4. **REPAIR STATE**: Document the exact state of the local database compared to the broker state to aid in post-mortem analysis.
