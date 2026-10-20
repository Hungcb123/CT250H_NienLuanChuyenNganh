CREATE TABLE equity_investment_preferences (
 user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 mode VARCHAR(8) NOT NULL CHECK (mode IN ('STOCKS','ETF','MIXED')),
 etf_weight NUMERIC(5,4) NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK ((mode='STOCKS' AND etf_weight=0) OR (mode='ETF' AND etf_weight=1)
     OR (mode='MIXED' AND etf_weight>0 AND etf_weight<1))
);
INSERT INTO assets(ticker,name,asset_class) VALUES('E1VFVN30','ETF DCVFMVN30','STOCK') ON CONFLICT(ticker) DO NOTHING;
