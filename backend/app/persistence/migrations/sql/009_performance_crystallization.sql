CREATE TABLE IF NOT EXISTS performance_compensation_lifecycle_policies (
    policy_id TEXT PRIMARY KEY,
    terms_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    crystallization_frequency TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    crystallize_on_termination INTEGER NOT NULL,
    effective_to TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (terms_id)
        REFERENCES performance_compensation_terms(terms_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(policy_id)) > 0),
    CHECK (length(trim(terms_id)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (
        crystallization_frequency IN (
            'MONTHLY',
            'QUARTERLY',
            'ANNUALLY',
            'TERMINATION_ONLY',
            'MANUAL_REVIEW'
        )
    ),
    CHECK (length(trim(effective_from)) > 0),
    CHECK (
        effective_to IS NULL
        OR length(trim(effective_to)) > 0
    ),
    CHECK (evidence_refs_json != '[]'),
    CHECK (crystallize_on_termination IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_performance_compensation_lifecycle_policies_terms
ON performance_compensation_lifecycle_policies(terms_id);

CREATE INDEX IF NOT EXISTS idx_performance_compensation_lifecycle_policies_created
ON performance_compensation_lifecycle_policies(created_at);

CREATE TABLE IF NOT EXISTS crystallization_assessments (
    policy_id TEXT NOT NULL,
    terms_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    assessed_at TEXT NOT NULL,
    shadow_entitlement_total TEXT NOT NULL,
    crystallizable_amount TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (policy_id, period_start, period_end),

    FOREIGN KEY (policy_id)
        REFERENCES performance_compensation_lifecycle_policies(policy_id)
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
    CHECK (length(trim(shadow_entitlement_total)) > 0),
    CHECK (length(trim(crystallizable_amount)) > 0),
    CHECK (
        status IN (
            'NOT_DUE',
            'ELIGIBLE',
            'BLOCKED',
            'EXPIRED'
        )
    ),
    CHECK (evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_crystallization_assessments_policy
ON crystallization_assessments(policy_id);

CREATE INDEX IF NOT EXISTS idx_crystallization_assessments_terms
ON crystallization_assessments(terms_id);

CREATE INDEX IF NOT EXISTS idx_crystallization_assessments_created
ON crystallization_assessments(created_at);
