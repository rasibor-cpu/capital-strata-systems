CREATE TABLE IF NOT EXISTS commercial_fx_conversion_evidence (
    fx_conversion_id TEXT NOT NULL PRIMARY KEY,
    source_currency TEXT NOT NULL,
    target_currency TEXT NOT NULL,
    source_amount TEXT NOT NULL,
    converted_amount TEXT NOT NULL,
    fx_rate TEXT NOT NULL,
    rate_effective_at TEXT NOT NULL,
    rate_source_reference TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (length(trim(fx_conversion_id)) > 0),
    CHECK (evidence_refs_json != '[]'),
    CHECK (target_currency = 'USD'),
    CHECK (source_currency != target_currency)
);
