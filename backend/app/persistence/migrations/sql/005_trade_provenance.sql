CREATE TABLE IF NOT EXISTS trade_provenance (
    trade_id TEXT PRIMARY KEY,
    advice_id TEXT,
    attribution_class TEXT NOT NULL,
    mandate_compliance TEXT NOT NULL,
    recommendation_timestamp TEXT,
    acceptance_timestamp TEXT,
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (trade_id)
        REFERENCES trades(trade_id)
        ON DELETE RESTRICT,

    CHECK (
        attribution_class IN (
            'CSS_ADVISED',
            'CSS_ADVISED_ACCEPTED',
            'CSS_MODIFIED',
            'CUSTOMER_DIRECTED',
            'EXTERNAL'
        )
    ),

    CHECK (
        mandate_compliance IN (
            'COMPLIANT',
            'MODIFIED',
            'OVERRIDDEN',
            'OUTSIDE_CSS',
            'UNVERIFIED'
        )
    ),

    CHECK (
        attribution_class != 'CSS_ADVISED_ACCEPTED'
        OR (
            advice_id IS NOT NULL
            AND length(trim(advice_id)) > 0
            AND mandate_compliance = 'COMPLIANT'
            AND acceptance_timestamp IS NOT NULL
            AND length(trim(acceptance_timestamp)) > 0
            AND evidence_refs_json != '[]'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_trade_provenance_advice
ON trade_provenance(advice_id);

CREATE INDEX IF NOT EXISTS idx_trade_provenance_attribution
ON trade_provenance(attribution_class);