CREATE TABLE IF NOT EXISTS commercial_technical_validations (
    validation_id TEXT PRIMARY KEY,
    commit_sha TEXT NOT NULL,
    validated_at TEXT NOT NULL,
    test_count INTEGER NOT NULL CHECK (test_count >= 0),
    full_regression_passed INTEGER NOT NULL CHECK (full_regression_passed IN (0,1)),
    governance_validation_passed INTEGER NOT NULL CHECK (governance_validation_passed IN (0,1)),
    commercialization_consistency_passed INTEGER NOT NULL CHECK (commercialization_consistency_passed IN (0,1)),
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_commercial_technical_validations_time
ON commercial_technical_validations (validated_at DESC, validation_id DESC);
