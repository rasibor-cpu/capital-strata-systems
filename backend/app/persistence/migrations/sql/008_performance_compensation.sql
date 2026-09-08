CREATE TABLE IF NOT EXISTS performance_compensation_terms (
    terms_id TEXT PRIMARY KEY,
    currency TEXT NOT NULL,
    performance_compensation_rate TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    evidence_refs_json TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    CHECK (length(trim(terms_id)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (length(trim(performance_compensation_rate)) > 0),
    CHECK (length(trim(effective_from)) > 0),
    CHECK (evidence_refs_json != '[]'),
    CHECK (accepted IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_performance_compensation_terms_created
ON performance_compensation_terms(created_at);

CREATE INDEX IF NOT EXISTS idx_performance_compensation_terms_currency
ON performance_compensation_terms(currency);

CREATE TABLE IF NOT EXISTS shadow_compensation_entitlements (
    trade_id TEXT PRIMARY KEY,
    terms_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    new_economic_gain TEXT NOT NULL,
    compensation_rate TEXT NOT NULL,
    shadow_compensation_amount TEXT NOT NULL,
    calculation_timestamp TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (terms_id)
        REFERENCES performance_compensation_terms(terms_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (trade_id)
        REFERENCES performance_accounting_transitions(trade_id)
        ON DELETE RESTRICT,

    CHECK (length(trim(trade_id)) > 0),
    CHECK (length(trim(terms_id)) > 0),
    CHECK (length(trim(currency)) > 0),
    CHECK (currency = upper(currency)),
    CHECK (length(trim(new_economic_gain)) > 0),
    CHECK (length(trim(compensation_rate)) > 0),
    CHECK (length(trim(shadow_compensation_amount)) > 0),
    CHECK (length(trim(calculation_timestamp)) > 0),
    CHECK (evidence_refs_json != '[]')
);

CREATE INDEX IF NOT EXISTS idx_shadow_compensation_entitlements_terms
ON shadow_compensation_entitlements(terms_id);

CREATE INDEX IF NOT EXISTS idx_shadow_compensation_entitlements_created
ON shadow_compensation_entitlements(created_at);
