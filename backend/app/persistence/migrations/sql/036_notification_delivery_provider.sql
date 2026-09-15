CREATE TABLE IF NOT EXISTS notification_delivery_provider_configurations (
    provider_id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    environment TEXT NOT NULL,
    provider_account_reference TEXT,
    approval_reference TEXT,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
