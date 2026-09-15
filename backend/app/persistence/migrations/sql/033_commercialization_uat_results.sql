CREATE TABLE IF NOT EXISTS commercialization_uat_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    scenario TEXT NOT NULL,
    status TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    environment_reference TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (run_id, scenario, executed_at)
);

CREATE INDEX IF NOT EXISTS idx_commercialization_uat_run
ON commercialization_uat_results (run_id, scenario, executed_at DESC);
