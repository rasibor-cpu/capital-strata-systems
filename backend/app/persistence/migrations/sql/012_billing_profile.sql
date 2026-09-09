CREATE TABLE IF NOT EXISTS commercial_billing_profiles (
    billing_profile_id TEXT PRIMARY KEY,
    terms_id TEXT NOT NULL,
    party_type TEXT NOT NULL,
    bill_to_name TEXT NOT NULL,
    bill_to_reference TEXT NOT NULL,
    seller_reference TEXT NOT NULL,
    tax_treatment_status TEXT NOT NULL,
    payment_terms_status TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    effective_to TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (terms_id)
        REFERENCES performance_compensation_terms(terms_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(billing_profile_id)) > 0),
    CHECK (length(trim(terms_id)) > 0),
    CHECK (
        party_type IN (
            'INDIVIDUAL',
            'ORGANIZATION'
        )
    ),
    CHECK (length(trim(bill_to_name)) > 0),
    CHECK (length(trim(bill_to_reference)) > 0),
    CHECK (length(trim(seller_reference)) > 0),
    CHECK (
        tax_treatment_status IN (
            'UNDETERMINED',
            'OUT_OF_SCOPE',
            'EXEMPT',
            'REQUIRES_DETERMINATION'
        )
    ),
    CHECK (
        payment_terms_status IN (
            'UNDETERMINED',
            'NOT_REQUIRED',
            'REQUIRES_DEFINITION',
            'DEFINED_EXTERNALLY'
        )
    ),
    CHECK (length(trim(effective_from)) > 0),
    CHECK (evidence_refs_json != '[]'),
    CHECK (
        effective_to IS NULL
        OR length(trim(effective_to)) > 0
    )
);

CREATE INDEX IF NOT EXISTS idx_commercial_billing_profiles_terms
ON commercial_billing_profiles(terms_id);

CREATE INDEX IF NOT EXISTS idx_commercial_billing_profiles_created
ON commercial_billing_profiles(created_at);
