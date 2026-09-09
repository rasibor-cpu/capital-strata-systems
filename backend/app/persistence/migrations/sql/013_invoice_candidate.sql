CREATE TABLE IF NOT EXISTS commercial_invoice_candidates (
    policy_id TEXT NOT NULL,
    terms_id TEXT NOT NULL,
    billing_profile_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    candidate_amount TEXT NOT NULL,
    assessed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (policy_id, period_start, period_end),

    FOREIGN KEY (policy_id, period_start, period_end)
        REFERENCES commercial_billable_obligations(
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

    CHECK (length(trim(policy_id)) > 0),
    CHECK (length(trim(terms_id)) > 0),
    CHECK (length(trim(billing_profile_id)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (length(trim(period_start)) > 0),
    CHECK (length(trim(period_end)) > 0),
    CHECK (length(trim(candidate_amount)) > 0),
    CHECK (length(trim(assessed_at)) > 0),
    CHECK (
        status IN (
            'NOT_READY',
            'READY',
            'BLOCKED',
            'EXPIRED'
        )
    ),
    CHECK (evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_candidates_policy
ON commercial_invoice_candidates(policy_id);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_candidates_terms
ON commercial_invoice_candidates(terms_id);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_candidates_profile
ON commercial_invoice_candidates(billing_profile_id);

CREATE INDEX IF NOT EXISTS idx_commercial_invoice_candidates_created
ON commercial_invoice_candidates(created_at);
