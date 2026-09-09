CREATE TABLE IF NOT EXISTS commercial_invoice_corrections (
    correction_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    correction_type TEXT NOT NULL,
    corrected_at TEXT NOT NULL,
    reason_reference TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    replacement_invoice_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (correction_id),

    FOREIGN KEY (invoice_id)
        REFERENCES commercial_invoice_issued_records(invoice_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (replacement_invoice_id)
        REFERENCES commercial_invoice_issued_records(invoice_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(correction_id)) > 0),
    CHECK (length(trim(invoice_id)) > 0),
    CHECK (length(trim(corrected_at)) > 0),
    CHECK (length(trim(reason_reference)) > 0),
    CHECK (evidence_refs_json != '[]'),
    CHECK (
        correction_type IN (
            'VOID',
            'SUPERSEDE'
        )
    ),
    CHECK (
        (
            correction_type = 'VOID'
            AND replacement_invoice_id IS NULL
        )
        OR (
            correction_type = 'SUPERSEDE'
            AND replacement_invoice_id IS NOT NULL
            AND replacement_invoice_id <> invoice_id
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_corrections_invoice
ON commercial_invoice_corrections(invoice_id);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_corrections_replacement
ON commercial_invoice_corrections(replacement_invoice_id);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_corrections_type
ON commercial_invoice_corrections(correction_type);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_corrections_created
ON commercial_invoice_corrections(created_at);
