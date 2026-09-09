CREATE TABLE IF NOT EXISTS commercial_receivable_payment_allocations (
    allocation_id TEXT NOT NULL,
    payment_id TEXT NOT NULL,
    receivable_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    allocated_amount TEXT NOT NULL,
    allocated_at TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (allocation_id),

    FOREIGN KEY (payment_id)
        REFERENCES commercial_receivable_payments(payment_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (receivable_id)
        REFERENCES commercial_receivable_recognitions(receivable_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (invoice_id)
        REFERENCES commercial_invoice_issued_records(invoice_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(allocation_id)) > 0),
    CHECK (length(trim(payment_id)) > 0),
    CHECK (length(trim(receivable_id)) > 0),
    CHECK (length(trim(invoice_id)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (length(trim(allocated_amount)) > 0),
    CHECK (length(trim(allocated_at)) > 0),
    CHECK (evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_payment_allocations_payment
ON commercial_receivable_payment_allocations(payment_id);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_payment_allocations_receivable
ON commercial_receivable_payment_allocations(receivable_id);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_payment_allocations_invoice
ON commercial_receivable_payment_allocations(invoice_id);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_payment_allocations_created
ON commercial_receivable_payment_allocations(created_at);
