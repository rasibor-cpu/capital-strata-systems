CREATE TABLE IF NOT EXISTS legal_acceptances (
    acceptance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    acceptance_type TEXT NOT NULL,
    acceptance_version TEXT NOT NULL,
    accepted INTEGER NOT NULL CHECK (accepted IN (0, 1)),
    accepted_at TEXT NOT NULL,
    audit_reference TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_legal_acceptances_user_type_time
ON legal_acceptances (
    user_id,
    acceptance_type,
    accepted_at DESC,
    acceptance_id DESC
);

CREATE INDEX IF NOT EXISTS idx_legal_acceptances_user_type_version_time
ON legal_acceptances (
    user_id,
    acceptance_type,
    acceptance_version,
    accepted_at DESC,
    acceptance_id DESC
);