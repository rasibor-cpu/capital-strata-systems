CREATE TABLE IF NOT EXISTS customer_notification_policies (
    policy_id TEXT PRIMARY KEY,
    jurisdiction_code TEXT NOT NULL,
    notification_type TEXT NOT NULL,
    lead_time_hours INTEGER NOT NULL CHECK (lead_time_hours >= 0),
    approved_for_production INTEGER NOT NULL CHECK (approved_for_production IN (0,1)),
    approval_reference TEXT,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS customer_notification_intents (
    notification_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    account_reference TEXT NOT NULL,
    notification_type TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS launch_evidence_items (
    dossier_id TEXT NOT NULL,
    category TEXT NOT NULL,
    evidence_reference TEXT NOT NULL,
    approved INTEGER NOT NULL CHECK (approved IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (dossier_id, category)
);

CREATE INDEX IF NOT EXISTS idx_customer_notification_policy
ON customer_notification_policies (
    jurisdiction_code,
    notification_type,
    approved_for_production
);

CREATE INDEX IF NOT EXISTS idx_customer_notification_intent
ON customer_notification_intents (
    customer_id,
    account_reference,
    scheduled_for
);
