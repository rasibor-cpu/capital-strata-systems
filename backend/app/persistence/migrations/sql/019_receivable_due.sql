CREATE TABLE IF NOT EXISTS commercial_receivable_due_records (
    due_record_id TEXT NOT NULL,
    receivable_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    due_date TEXT NOT NULL,
    determined_at TEXT NOT NULL,
    terms_reference TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (due_record_id),

    UNIQUE (receivable_id),

    FOREIGN KEY (receivable_id)
        REFERENCES commercial_receivable_recognitions(receivable_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (invoice_id)
        REFERENCES commercial_invoice_issued_records(invoice_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(due_record_id)) > 0),
    CHECK (length(trim(receivable_id)) > 0),
    CHECK (length(trim(invoice_id)) > 0),
    CHECK (length(trim(due_date)) > 0),
    CHECK (length(due_date) = 10),
    CHECK (substr(due_date, 5, 1) = '-'),
    CHECK (substr(due_date, 8, 1) = '-'),
    CHECK (length(trim(determined_at)) > 0),
    CHECK (length(trim(terms_reference)) > 0),
    CHECK (evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_due_records_invoice
ON commercial_receivable_due_records(invoice_id);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_due_records_created
ON commercial_receivable_due_records(created_at);
