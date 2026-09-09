CREATE TABLE IF NOT EXISTS commercial_receivable_credits (
    credit_id TEXT NOT NULL,
    receivable_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    credit_amount TEXT NOT NULL,
    credited_at TEXT NOT NULL,
    reason_reference TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (credit_id),

    FOREIGN KEY (receivable_id)
        REFERENCES commercial_receivable_recognitions(receivable_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (invoice_id)
        REFERENCES commercial_invoice_issued_records(invoice_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(credit_id)) > 0),
    CHECK (length(trim(receivable_id)) > 0),
    CHECK (length(trim(invoice_id)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (length(trim(credit_amount)) > 0),
    CHECK (length(trim(credited_at)) > 0),
    CHECK (length(trim(reason_reference)) > 0),
    CHECK (evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_credits_receivable
ON commercial_receivable_credits(receivable_id);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_credits_invoice
ON commercial_receivable_credits(invoice_id);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_credits_created
ON commercial_receivable_credits(created_at);
