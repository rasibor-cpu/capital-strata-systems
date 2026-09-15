CREATE TABLE IF NOT EXISTS production_security_operational_certifications (
    certification_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    certified_at TEXT NOT NULL,
    secrets_management_verified INTEGER NOT NULL CHECK (secrets_management_verified IN (0,1)),
    tls_transport_verified INTEGER NOT NULL CHECK (tls_transport_verified IN (0,1)),
    access_control_verified INTEGER NOT NULL CHECK (access_control_verified IN (0,1)),
    audit_logging_verified INTEGER NOT NULL CHECK (audit_logging_verified IN (0,1)),
    monitoring_alerting_verified INTEGER NOT NULL CHECK (monitoring_alerting_verified IN (0,1)),
    backup_restore_tested INTEGER NOT NULL CHECK (backup_restore_tested IN (0,1)),
    rollback_tested INTEGER NOT NULL CHECK (rollback_tested IN (0,1)),
    reconciliation_verified INTEGER NOT NULL CHECK (reconciliation_verified IN (0,1)),
    incident_response_verified INTEGER NOT NULL CHECK (incident_response_verified IN (0,1)),
    dependency_vulnerability_reviewed INTEGER NOT NULL CHECK (dependency_vulnerability_reviewed IN (0,1)),
    reviewer_reference TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payment_provider_configurations (
    provider_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    environment TEXT NOT NULL,
    provider_account_reference TEXT,
    approval_reference TEXT,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_security_certification_time
ON production_security_operational_certifications (
    certified_at DESC,
    certification_id DESC
);
