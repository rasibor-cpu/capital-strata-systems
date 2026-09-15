CREATE TABLE IF NOT EXISTS independent_trade_economics (
    trade_id TEXT PRIMARY KEY,
    account_reference TEXT NOT NULL,
    calculation_timestamp TEXT NOT NULL,
    attribution_class TEXT NOT NULL,
    realized_pnl TEXT NOT NULL,
    currency TEXT NOT NULL,
    platform_charge_rate TEXT NOT NULL,
    platform_charge_amount TEXT NOT NULL,
    charge_basis TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_independent_trade_economics_account_time
ON independent_trade_economics (
    account_reference,
    calculation_timestamp,
    trade_id
);
