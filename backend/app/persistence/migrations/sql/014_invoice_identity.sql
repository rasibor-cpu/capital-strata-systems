CREATE TABLE IF NOT EXISTS commercial_invoice_identity_allocations (
    invoice_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    terms_id TEXT NOT NULL,
    billing_profile_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    invoice_amount TEXT NOT NULL,
    allocated_at TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    invoice_number TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (invoice_id),

    UNIQUE (policy_id, period_start, period_end),
    UNIQUE (invoice_number),

    FOREIGN KEY (policy_id, period_start, period_end)
        REFERENCES commercial_invoice_candidates(
            policy_id,
            period_start,
            period_end
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
    CHECK (length(trim(allocated_at)) > 0),
    CHECK (evidence_refs_json != '[]'),
    CHECK (
        invoice_number IS NULL
        OR length(trim(invoice_number)) > 0
    )
);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_identity_policy
ON commercial_invoice_identity_allocations(policy_id);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_identity_terms
ON commercial_invoice_identity_allocations(terms_id);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_identity_profile
ON commercial_invoice_identity_allocations(billing_profile_id);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_identity_created
ON commercial_invoice_identity_allocations(created_at);
