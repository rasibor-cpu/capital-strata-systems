CREATE TABLE IF NOT EXISTS commercial_billable_obligations (
    policy_id TEXT NOT NULL,
    terms_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    billable_amount TEXT NOT NULL,
    recognized_at TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (policy_id, period_start, period_end),

    FOREIGN KEY (policy_id, period_start, period_end)
        REFERENCES commercial_settlement_readiness(
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
    CHECK (length(trim(recognized_at)) > 0),
    CHECK (length(trim(billable_amount)) > 0),
    CHECK (
        status IN (
            'NOT_BILLABLE',
            'BILLABLE',
            'BLOCKED',
            'EXPIRED'
        )
    ),
    CHECK (evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_commercial_billable_obligations_policy
ON commercial_billable_obligations(policy_id);

CREATE INDEX IF NOT EXISTS idx_commercial_billable_obligations_terms
ON commercial_billable_obligations(terms_id);

CREATE INDEX IF NOT EXISTS idx_commercial_billable_obligations_created
ON commercial_billable_obligations(created_at);
