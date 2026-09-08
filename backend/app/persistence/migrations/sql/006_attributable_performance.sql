CREATE TABLE IF NOT EXISTS attributable_performance (
    trade_id TEXT PRIMARY KEY,
    advice_id TEXT NOT NULL,
    realized_pnl TEXT NOT NULL,
    currency TEXT NOT NULL,
    verification_timestamp TEXT NOT NULL,
    provenance_evidence_refs_json TEXT NOT NULL,
    economics_evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (trade_id)
        REFERENCES trades(trade_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (trade_id)
        REFERENCES trade_provenance(trade_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(advice_id)) > 0),
    CHECK (length(trim(realized_pnl)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (length(trim(verification_timestamp)) > 0),
    CHECK (provenance_evidence_refs_json != '[]'),
    CHECK (economics_evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_attributable_performance_advice
ON attributable_performance(advice_id);

CREATE INDEX IF NOT EXISTS idx_attributable_performance_created
ON attributable_performance(created_at);
