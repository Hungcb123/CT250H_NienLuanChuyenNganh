-- ============================================================================
-- V3__create_portfolio_snapshots.sql
-- Daily Portfolio NAV Snapshots for Growth Curve & Risk Metrics Analysis
-- ============================================================================

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    total_nav NUMERIC(19, 4) NOT NULL DEFAULT 0.0000,
    stock_value NUMERIC(19, 4) DEFAULT 0.0000,
    gold_value NUMERIC(19, 4) DEFAULT 0.0000,
    savings_value NUMERIC(19, 4) DEFAULT 0.0000,
    cash_value NUMERIC(19, 4) DEFAULT 0.0000,
    vnindex_value NUMERIC(19, 4) DEFAULT 1280.0000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_snapshot_date UNIQUE (user_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_user_date ON portfolio_snapshots(user_id, snapshot_date DESC);
