CREATE TABLE IF NOT EXISTS commercial_agreement_snapshots (
    agreement_id TEXT NOT NULL,
    agreement_version TEXT NOT NULL,
    jurisdiction_code TEXT NOT NULL,
    pricing_plan_id TEXT NOT NULL,
    pricing_summary TEXT NOT NULL,
    trial_duration_days INTEGER NOT NULL CHECK (trial_duration_days > 0),
    automatic_conversion_disclosure TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (agreement_id, agreement_version)
);

CREATE TABLE IF NOT EXISTS commercial_trial_enrollments (
    customer_id TEXT NOT NULL,
    account_reference TEXT NOT NULL,
    agreement_id TEXT NOT NULL,
    agreement_version TEXT NOT NULL,
    pricing_plan_id TEXT NOT NULL,
    accepted_at TEXT NOT NULL,
    trial_start_at TEXT NOT NULL,
    trial_expires_at TEXT NOT NULL,
    displayed_pricing_summary TEXT NOT NULL,
    displayed_conversion_disclosure TEXT NOT NULL,
    acceptance_audit_reference TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (customer_id, account_reference, agreement_id, agreement_version),
    FOREIGN KEY (agreement_id, agreement_version)
        REFERENCES commercial_agreement_snapshots (agreement_id, agreement_version)
);

CREATE TABLE IF NOT EXISTS commercial_trial_cancellations (
    cancellation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    account_reference TEXT NOT NULL,
    canceled_at TEXT NOT NULL,
    cancellation_audit_reference TEXT NOT NULL UNIQUE,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_commercial_trial_enrollment_account
ON commercial_trial_enrollments (account_reference, trial_expires_at);

CREATE INDEX IF NOT EXISTS idx_commercial_trial_cancellation_account
ON commercial_trial_cancellations (
    customer_id,
    account_reference,
    canceled_at DESC,
    cancellation_id DESC
);
