CREATE TABLE IF NOT EXISTS commercial_receivable_reversals (
    reversal_id TEXT NOT NULL,
    receivable_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    correction_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    reversal_amount TEXT NOT NULL,
    reversed_at TEXT NOT NULL,
    reason_reference TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (reversal_id),

    UNIQUE (receivable_id),

    FOREIGN KEY (receivable_id)
        REFERENCES commercial_receivable_recognitions(receivable_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (invoice_id)
        REFERENCES commercial_invoice_issued_records(invoice_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (correction_id)
        REFERENCES commercial_invoice_corrections(correction_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(reversal_id)) > 0),
    CHECK (length(trim(receivable_id)) > 0),
    CHECK (length(trim(invoice_id)) > 0),
    CHECK (length(trim(correction_id)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (length(trim(reversal_amount)) > 0),
    CHECK (length(trim(reversed_at)) > 0),
    CHECK (length(trim(reason_reference)) > 0),
    CHECK (evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_reversals_invoice
ON commercial_receivable_reversals(invoice_id);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_reversals_correction
ON commercial_receivable_reversals(correction_id);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_reversals_created
ON commercial_receivable_reversals(created_at);
