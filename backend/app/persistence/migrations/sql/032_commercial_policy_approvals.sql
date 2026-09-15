CREATE TABLE IF NOT EXISTS independent_platform_charge_policies (
    policy_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    rate TEXT NOT NULL,
    currency TEXT NOT NULL,
    approved_for_production INTEGER NOT NULL CHECK (approved_for_production IN (0,1)),
    approved_at TEXT,
    approval_reference TEXT,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_independent_platform_policy_approval
ON independent_platform_charge_policies (
    approved_for_production,
    currency,
    policy_id
);

CREATE TABLE IF NOT EXISTS jurisdiction_service_mode_approvals (
    approval_id TEXT PRIMARY KEY,
    jurisdiction_code TEXT NOT NULL,
    service_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    approved_at TEXT,
    approval_reference TEXT,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (jurisdiction_code, service_mode, approval_id)
);

CREATE INDEX IF NOT EXISTS idx_jurisdiction_service_mode
ON jurisdiction_service_mode_approvals (
    jurisdiction_code,
    service_mode,
    created_at DESC
);
