CREATE TABLE IF NOT EXISTS performance_accounting_transitions (
    trade_id TEXT PRIMARY KEY,
    currency TEXT NOT NULL,

    previous_cumulative_attributable_pnl TEXT NOT NULL,
    previous_high_water_mark TEXT NOT NULL,
    previous_loss_carryforward TEXT NOT NULL,

    attributable_realized_pnl TEXT NOT NULL,
    recovered_loss TEXT NOT NULL,
    new_economic_gain TEXT NOT NULL,

    new_cumulative_attributable_pnl TEXT NOT NULL,
    new_high_water_mark TEXT NOT NULL,
    new_loss_carryforward TEXT NOT NULL,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (trade_id)
        REFERENCES attributable_performance(trade_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),

    CHECK (length(trim(previous_cumulative_attributable_pnl)) > 0),
    CHECK (length(trim(previous_high_water_mark)) > 0),
    CHECK (length(trim(previous_loss_carryforward)) > 0),

    CHECK (length(trim(attributable_realized_pnl)) > 0),
    CHECK (length(trim(recovered_loss)) > 0),
    CHECK (length(trim(new_economic_gain)) > 0),

    CHECK (length(trim(new_cumulative_attributable_pnl)) > 0),
    CHECK (length(trim(new_high_water_mark)) > 0),
    CHECK (length(trim(new_loss_carryforward)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_performance_accounting_transitions_created
ON performance_accounting_transitions(created_at);

CREATE INDEX IF NOT EXISTS idx_performance_accounting_transitions_currency
ON performance_accounting_transitions(currency);
