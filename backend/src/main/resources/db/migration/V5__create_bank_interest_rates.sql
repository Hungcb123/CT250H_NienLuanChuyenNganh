-- V5: Bảng Biểu lãi suất tiết kiệm các Ngân hàng và Chỉ số Vĩ mô (Rf)
CREATE TABLE bank_interest_rates (
    id BIGSERIAL PRIMARY KEY,
    bank_code VARCHAR(32) NOT NULL,
    bank_name VARCHAR(128) NOT NULL,
    term_months INT NOT NULL,
    interest_rate NUMERIC(6, 2) NOT NULL,
    effective_date DATE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_bank_term_date UNIQUE (bank_code, term_months, effective_date)
);

CREATE INDEX idx_bank_interest_rates_term_date ON bank_interest_rates(term_months, effective_date DESC);
CREATE INDEX idx_bank_interest_rates_bank ON bank_interest_rates(bank_code, effective_date DESC);

CREATE TABLE macro_indicators (
    id BIGSERIAL PRIMARY KEY,
    indicator_code VARCHAR(64) NOT NULL,
    indicator_name VARCHAR(128) NOT NULL,
    indicator_value NUMERIC(10, 4) NOT NULL,
    unit VARCHAR(32) DEFAULT '%',
    recorded_date DATE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_macro_code_date UNIQUE (indicator_code, recorded_date)
);

-- Seed dữ liệu khởi tạo biểu lãi suất ngân hàng (thực tế các ngân hàng lớn)
INSERT INTO bank_interest_rates (bank_code, bank_name, term_months, interest_rate, effective_date) VALUES
-- Vietcombank
('VCB', 'Vietcombank', 1, 3.10, CURRENT_DATE),
('VCB', 'Vietcombank', 3, 3.40, CURRENT_DATE),
('VCB', 'Vietcombank', 6, 4.50, CURRENT_DATE),
('VCB', 'Vietcombank', 12, 5.20, CURRENT_DATE),

-- BIDV
('BID', 'BIDV', 1, 3.20, CURRENT_DATE),
('BID', 'BIDV', 3, 3.50, CURRENT_DATE),
('BID', 'BIDV', 6, 4.60, CURRENT_DATE),
('BID', 'BIDV', 12, 5.30, CURRENT_DATE),

-- VietinBank
('CTG', 'VietinBank', 1, 3.20, CURRENT_DATE),
('CTG', 'VietinBank', 3, 3.50, CURRENT_DATE),
('CTG', 'VietinBank', 6, 4.60, CURRENT_DATE),
('CTG', 'VietinBank', 12, 5.30, CURRENT_DATE),

-- Agribank
('AGR', 'Agribank', 1, 3.20, CURRENT_DATE),
('AGR', 'Agribank', 3, 3.50, CURRENT_DATE),
('AGR', 'Agribank', 6, 4.70, CURRENT_DATE),
('AGR', 'Agribank', 12, 5.40, CURRENT_DATE),

-- MB Bank
('MBB', 'MB Bank', 1, 3.50, CURRENT_DATE),
('MBB', 'MB Bank', 3, 3.90, CURRENT_DATE),
('MBB', 'MB Bank', 6, 5.10, CURRENT_DATE),
('MBB', 'MB Bank', 12, 5.70, CURRENT_DATE),

-- Techcombank
('TCB', 'Techcombank', 1, 3.45, CURRENT_DATE),
('TCB', 'Techcombank', 3, 3.85, CURRENT_DATE),
('TCB', 'Techcombank', 6, 5.20, CURRENT_DATE),
('TCB', 'Techcombank', 12, 5.65, CURRENT_DATE),

-- ACB
('ACB', 'ACB', 1, 3.30, CURRENT_DATE),
('ACB', 'ACB', 3, 3.70, CURRENT_DATE),
('ACB', 'ACB', 6, 5.00, CURRENT_DATE),
('ACB', 'ACB', 12, 5.50, CURRENT_DATE),

-- HDBank
('HDB', 'HDBank', 1, 3.60, CURRENT_DATE),
('HDB', 'HDBank', 3, 4.00, CURRENT_DATE),
('HDB', 'HDBank', 6, 5.40, CURRENT_DATE),
('HDB', 'HDBank', 12, 6.00, CURRENT_DATE)
ON CONFLICT (bank_code, term_months, effective_date) DO NOTHING;

-- Seed Chỉ số lãi suất phi rủi ro liên ngân hàng (SBV Interbank Overnight/1W Repo)
INSERT INTO macro_indicators (indicator_code, indicator_name, indicator_value, unit, recorded_date) VALUES
('RF_INTERBANK_RATE', 'Lãi suất phi rủi ro (SBV Interbank Rate)', 4.5000, '%', CURRENT_DATE)
ON CONFLICT (indicator_code, recorded_date) DO NOTHING;
