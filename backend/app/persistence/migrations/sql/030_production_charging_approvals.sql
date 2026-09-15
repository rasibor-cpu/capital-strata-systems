CREATE TABLE IF NOT EXISTS commercial_jurisdiction_legal_reviews (
    legal_review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    jurisdiction_code TEXT NOT NULL,
    agreement_id TEXT NOT NULL,
    agreement_version TEXT NOT NULL,
    status TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    reviewer_reference TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (jurisdiction_code, agreement_id, agreement_version, reviewer_reference)
);

CREATE TABLE IF NOT EXISTS commercial_production_certifications (
    certification_id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL,
    agreement_version TEXT NOT NULL,
    jurisdiction_code TEXT NOT NULL,
    status TEXT NOT NULL,
    certified_at TEXT NOT NULL,
    reconciliation_verified INTEGER NOT NULL CHECK (reconciliation_verified IN (0,1)),
    security_release_blockers_clear INTEGER NOT NULL CHECK (security_release_blockers_clear IN (0,1)),
    charging_controls_verified INTEGER NOT NULL CHECK (charging_controls_verified IN (0,1)),
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS commercial_payment_collection_authorities (
    authority_id TEXT PRIMARY KEY,
    agreement_id TEXT NOT NULL,
    agreement_version TEXT NOT NULL,
    jurisdiction_code TEXT NOT NULL,
    status TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    authority_reference TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_legal_review_scope
ON commercial_jurisdiction_legal_reviews (
    jurisdiction_code, agreement_id, agreement_version, reviewed_at DESC
);

CREATE INDEX IF NOT EXISTS idx_production_certification_scope
ON commercial_production_certifications (
    jurisdiction_code, agreement_id, agreement_version, certified_at DESC
);

CREATE INDEX IF NOT EXISTS idx_payment_authority_scope
ON commercial_payment_collection_authorities (
    jurisdiction_code, agreement_id, agreement_version, approved_at DESC
);
