CREATE TABLE daily_market_sync_runs (
    sync_date DATE NOT NULL,
    market VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 1,
    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    detail VARCHAR(255),
    PRIMARY KEY(sync_date, market)
);
