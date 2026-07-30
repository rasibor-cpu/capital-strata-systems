-- MW-001 / RR-001: Persist equity_peak on PnL snapshots for RiskGovernor / ExecutionGate.
-- Non-destructive: adds column; backfills existing rows to equity (peak was never stored).

ALTER TABLE pnl_snapshots ADD COLUMN equity_peak TEXT NOT NULL DEFAULT '0';

UPDATE pnl_snapshots
SET equity_peak = equity
WHERE equity_peak = '0';
