CREATE TABLE IF NOT EXISTS commercial_receivable_recognitions (
    receivable_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    billing_profile_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    receivable_amount TEXT NOT NULL,
    recognized_at TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (receivable_id),

    UNIQUE (invoice_id),

    FOREIGN KEY (invoice_id)
        REFERENCES commercial_invoice_issued_records(invoice_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (billing_profile_id)
        REFERENCES commercial_billing_profiles(billing_profile_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(receivable_id)) > 0),
    CHECK (length(trim(invoice_id)) > 0),
    CHECK (length(trim(billing_profile_id)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (length(trim(receivable_amount)) > 0),
    CHECK (length(trim(recognized_at)) > 0),
    CHECK (evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_recognitions_profile
ON commercial_receivable_recognitions(billing_profile_id);

CREATE INDEX IF NOT EXISTS idx_commercial_receivable_recognitions_created
ON commercial_receivable_recognitions(created_at);
