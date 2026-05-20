CREATE TABLE IF NOT EXISTS pnl_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    broker_name TEXT NOT NULL,
    broker_mode TEXT NOT NULL,

    realized_pnl TEXT NOT NULL DEFAULT '0',
    unrealized_pnl TEXT NOT NULL DEFAULT '0',
    equity TEXT NOT NULL DEFAULT '0',
    available_cash TEXT NOT NULL DEFAULT '0',

    open_positions INTEGER NOT NULL DEFAULT 0,
    winning_positions INTEGER NOT NULL DEFAULT 0,
    losing_positions INTEGER NOT NULL DEFAULT 0,

    snapshot_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (session_id)
        REFERENCES sessions(session_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pnl_snapshots_session
ON pnl_snapshots(session_id);

CREATE INDEX IF NOT EXISTS idx_pnl_snapshots_created
ON pnl_snapshots(created_at);

CREATE INDEX IF NOT EXISTS idx_pnl_snapshots_account
ON pnl_snapshots(account_id);