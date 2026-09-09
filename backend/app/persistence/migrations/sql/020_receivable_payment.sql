CREATE TABLE IF NOT EXISTS commercial_receivable_payments (
    payment_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    payment_amount TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    external_reference TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (payment_id),

    CHECK (length(trim(payment_id)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (length(trim(payment_amount)) > 0),
    CHECK (length(trim(observed_at)) > 0),
    CHECK (length(trim(external_reference)) > 0),
    CHECK (evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_payments_external_ref
ON commercial_receivable_payments(external_reference);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_payments_created
ON commercial_receivable_payments(created_at);
