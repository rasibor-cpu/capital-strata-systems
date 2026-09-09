-- COM-002U: caller-supplied immutable terms; no seeded price or launch date.
-- Append-only repository API follows performance_compensation_terms.
CREATE TABLE IF NOT EXISTS platform_access_fee_terms (
    access_terms_id TEXT NOT NULL PRIMARY KEY,
    billing_currency TEXT NOT NULL,
    access_fee_amount TEXT NOT NULL,
    billing_frequency TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    evidence_refs_json TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    CHECK (length(trim(access_terms_id)) > 0),
    CHECK (access_terms_id = trim(access_terms_id)),
    CHECK (billing_currency = 'USD'),
    CHECK (length(trim(access_fee_amount)) > 0),
    CHECK (billing_frequency = 'MONTHLY'),
    CHECK (length(trim(effective_from)) > 0),
    CHECK (evidence_refs_json != '[]'),
    CHECK (accepted IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_platform_access_fee_terms_created
ON platform_access_fee_terms(created_at);
