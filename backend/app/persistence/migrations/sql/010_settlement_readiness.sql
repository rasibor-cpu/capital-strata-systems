CREATE TABLE IF NOT EXISTS commercial_settlement_readiness (
    policy_id TEXT NOT NULL,
    terms_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    crystallizable_amount TEXT NOT NULL,
    assessed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (policy_id, period_start, period_end),

    FOREIGN KEY (policy_id, period_start, period_end)
        REFERENCES crystallization_assessments(
            policy_id,
            period_start,
            period_end
        )
        ON DELETE RESTRICT,

    FOREIGN KEY (terms_id)
        REFERENCES performance_compensation_terms(terms_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(policy_id)) > 0),
    CHECK (length(trim(terms_id)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (length(trim(period_start)) > 0),
    CHECK (length(trim(period_end)) > 0),
    CHECK (length(trim(assessed_at)) > 0),
    CHECK (length(trim(crystallizable_amount)) > 0),
    CHECK (
        status IN (
            'NOT_READY',
            'PENDING_APPROVAL',
            'READY',
            'BLOCKED',
            'EXPIRED'
        )
    ),
    CHECK (evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_commercial_settlement_readiness_policy
ON commercial_settlement_readiness(policy_id);

CREATE INDEX IF NOT EXISTS idx_commercial_settlement_readiness_terms
ON commercial_settlement_readiness(terms_id);

CREATE INDEX IF NOT EXISTS idx_commercial_settlement_readiness_created
ON commercial_settlement_readiness(created_at);
