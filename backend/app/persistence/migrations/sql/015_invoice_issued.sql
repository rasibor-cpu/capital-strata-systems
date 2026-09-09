CREATE TABLE IF NOT EXISTS commercial_invoice_issued_records (
    invoice_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    terms_id TEXT NOT NULL,
    billing_profile_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    invoice_amount TEXT NOT NULL,
    invoice_number TEXT,
    issued_at TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (invoice_id),

    FOREIGN KEY (invoice_id)
        REFERENCES commercial_invoice_identity_allocations(
            invoice_id
        )
        ON DELETE RESTRICT,

    FOREIGN KEY (billing_profile_id)
        REFERENCES commercial_billing_profiles(
            billing_profile_id
        )
        ON DELETE RESTRICT,

    FOREIGN KEY (terms_id)
        REFERENCES performance_compensation_terms(terms_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(invoice_id)) > 0),
    CHECK (length(trim(policy_id)) > 0),
    CHECK (length(trim(terms_id)) > 0),
    CHECK (length(trim(billing_profile_id)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (length(trim(period_start)) > 0),
    CHECK (length(trim(period_end)) > 0),
    CHECK (length(trim(invoice_amount)) > 0),
    CHECK (length(trim(issued_at)) > 0),
    CHECK (evidence_refs_json != '[]'),
    CHECK (
        invoice_number IS NULL
        OR length(trim(invoice_number)) > 0
    )
);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_issued_policy
ON commercial_invoice_issued_records(policy_id);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_issued_terms
ON commercial_invoice_issued_records(terms_id);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_issued_profile
ON commercial_invoice_issued_records(billing_profile_id);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_issued_number
ON commercial_invoice_issued_records(invoice_number);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_issued_created
ON commercial_invoice_issued_records(created_at);
