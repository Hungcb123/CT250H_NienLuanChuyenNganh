-- ============================================================================
-- V1__init_schema.sql
-- Master Schema Migration for EquiFolio Platform
-- ============================================================================

-- Kích hoạt extension pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Bảng Người dùng hệ thống & Khẩu vị rủi ro
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    risk_score INT DEFAULT 50,                         -- Khảo sát rủi ro (0 - 100)
    risk_aversion_lambda NUMERIC(5, 2) DEFAULT 5.00,    -- Hệ số ngại rủi ro λ (1.0 đến 10.0)
    risk_profile VARCHAR(32) DEFAULT 'BALANCED',       -- 'CONSERVATIVE', 'BALANCED', 'GROWTH'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Bảng Tỷ trọng Mục tiêu (Dùng cho SAA/TAA & Phát hiện lệch Drift Detection)
CREATE TABLE portfolio_targets (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset_class VARCHAR(32) NOT NULL,                  -- 'STOCK', 'GOLD', 'CASH_SAVINGS'
    target_weight NUMERIC(5, 4) NOT NULL,              -- Ví dụ: 0.4000 (40%)
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_target_class UNIQUE (user_id, asset_class)
);

-- 3. Bảng Danh mục Tài sản hợp lệ
CREATE TABLE assets (
    ticker VARCHAR(32) PRIMARY KEY,                    -- 'VND', 'HPG', 'VCB', 'GOLD_SJC', v.v.
    name VARCHAR(100) NOT NULL,
    asset_class VARCHAR(32) NOT NULL                   -- 'CASH', 'STOCK', 'GOLD', 'SAVINGS'
);

-- 4. Bảng Lịch sử Giá thị trường & Định giá NAV hàng ngày
CREATE TABLE market_prices (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(32) NOT NULL REFERENCES assets(ticker),
    price NUMERIC(19, 4) NOT NULL,                     -- Giá khớp đóng cửa gần nhất
    trade_date DATE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_ticker_date UNIQUE (ticker, trade_date)
);
CREATE INDEX idx_market_prices_ticker_date ON market_prices(ticker, trade_date DESC);

-- 5. Bảng Tài khoản con (Sub-accounts trong Sổ cái)
CREATE TABLE accounts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_code VARCHAR(64) NOT NULL,                 -- 'VND_WALLET', 'EQUITY_CAPITAL', 'STOCK_HPG', 'GOLD_SJC'
    asset_type VARCHAR(32) NOT NULL REFERENCES assets(ticker),
    balance NUMERIC(19, 4) NOT NULL DEFAULT 0.0000,
    version BIGINT NOT NULL DEFAULT 0,                 -- Optimistic Locking (@Version)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_account UNIQUE (user_id, account_code)
);

-- 6. Bảng Giao dịch tài chính tổng quát
CREATE TABLE transactions (
    id BIGSERIAL PRIMARY KEY,
    transaction_code VARCHAR(64) NOT NULL UNIQUE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(32) NOT NULL,                         -- 'CAPITAL_INJECTION', 'BUY', 'SELL', 'REBALANCE'
    status VARCHAR(32) NOT NULL,                       -- 'PENDING', 'POSTED', 'FAILED'
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Bảng các dòng Bút toán Kép (Entries)
CREATE TABLE entries (
    id BIGSERIAL PRIMARY KEY,
    transaction_id BIGINT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    amount NUMERIC(19, 4) NOT NULL,                    -- Dương: Nợ (Debit), Âm: Có (Credit)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_entries_account_id ON entries(account_id);
CREATE INDEX idx_entries_tx_id ON entries(transaction_id);

-- 8. Bảng Sổ tiền gửi tiết kiệm & Cơ chế Lãi kép
CREATE TABLE savings_deposits (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    bank_name VARCHAR(64) NOT NULL,
    principal_amount NUMERIC(19, 4) NOT NULL,          -- Số tiền gốc gửi ban đầu
    interest_rate NUMERIC(5, 2) NOT NULL,              -- Lãi suất %/năm (Ví dụ: 6.00)
    term_months INT NOT NULL,                          -- Kỳ hạn gửi (1, 3, 6, 12 tháng)
    start_date DATE NOT NULL,
    maturity_date DATE NOT NULL,                       -- Ngày đáo hạn
    auto_rollover BOOLEAN NOT NULL DEFAULT TRUE,       -- TRUE: Tự động nhập lãi vào gốc (Lãi kép)
    accrued_interest NUMERIC(19, 4) NOT NULL DEFAULT 0.0000, -- Lãi lũy kế tạm tính hàng ngày
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',      -- 'ACTIVE', 'SETTLED', 'CLOSED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_savings_user_maturity ON savings_deposits(user_id, maturity_date, status);

-- 9. Bảng Transactional Outbox
CREATE TABLE outbox_events (
    id UUID PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',      -- 'PENDING', 'SENT'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_outbox_status_created ON outbox_events(status, created_at);

-- 10. Bảng Vector Store nâng cấp cho Hybrid Search
CREATE TABLE vector_store (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,                             -- Trích đoạn cẩm nang tri thức tài chính
    metadata JSONB,                                    -- Metadata lọc nghiệp vụ: {"topic": "GOLD"}
    embedding VECTOR(1536),                            -- Không gian nhúng vector (OpenAI 1536 chiều)
    tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED
);
CREATE INDEX idx_vector_store_hnsw ON vector_store USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_vector_store_tsv ON vector_store USING gin (tsv);
