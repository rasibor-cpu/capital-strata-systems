CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    broker_name TEXT NOT NULL,
    broker_mode TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    status TEXT NOT NULL,
    order_type TEXT NOT NULL,
    quantity TEXT NOT NULL,
    filled_quantity TEXT NOT NULL,
    entry_price TEXT NOT NULL,
    exit_price TEXT,
    commission TEXT NOT NULL DEFAULT '0',
    realized_pnl TEXT NOT NULL DEFAULT '0',
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    raw_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (session_id)
        REFERENCES sessions(session_id)
        ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_open_trade_session_symbol_direction
ON trades(session_id, symbol, direction)
WHERE status IN ('pending', 'open', 'partially_filled');

CREATE INDEX IF NOT EXISTS idx_trades_session
ON trades(session_id);

CREATE INDEX IF NOT EXISTS idx_trades_symbol
ON trades(symbol);

CREATE INDEX IF NOT EXISTS idx_trades_status
ON trades(status);

CREATE INDEX IF NOT EXISTS idx_trades_opened_at
ON trades(opened_at);