# Phase 114B: Controlled Paper Validation Runbook

## 1. Startup Checklist
- [ ] Verify execution environment is clean and target branch is `css-evening-consolidation-2026-06-09`.
- [ ] Verify `python -m pytest` passes all 388 integration tests.
- [ ] Ensure `.env.paper` is fully populated with practice-only credentials.
- [ ] Ensure `.env.live` is logically segregated.

## 2. Authentication Validation
- [ ] Launch `python scripts/css_live_dashboard.py`.
- [ ] Verify the standard CSS operator credential prompt is active.
- [ ] Confirm incorrect operator credentials fail cleanly.
- [ ] Confirm valid authentication establishes the session successfully.

## 3. Broker Validation
- [ ] Select `PAPER` mode explicitly during initialization.
- [ ] Verify that the initialization logs report connection to OANDA practice and/or Coinbase sandbox URLs ONLY.
- [ ] Ensure no live API keys are loaded or accessed.
- [ ] Confirm broker balance mapping binds accurately.

## 4. Dashboard Validation
- [ ] Confirm the HUD renders without throwing exceptions.
- [ ] Verify asset stream ticks update correctly.
- [ ] Ensure PnL metrics map to the canonical persistence layer without hallucinated numbers.

## 5. Trade Lifecycle Validation
- [ ] Monitor the intelligence queue for trade signal generation.
- [ ] Follow a single trade from proposal -> risk gate -> execution gate -> position book.
- [ ] Manually verify that cost, spread, and slippage are correctly deducted in paper execution matching the PnL definitions.
- [ ] Await the adaptive threshold or stop-loss trigger to verify the exit engine fires accurately.

## 6. Shutdown Checklist
- [ ] Trigger graceful shutdown via the dashboard UI or `Ctrl+C`.
- [ ] Verify all open execution loops terminate gracefully.
- [ ] Verify the final `PnlSnapshot` is successfully persisted to the unified session file.
- [ ] Archive the `audit.log` for evidence collection.
