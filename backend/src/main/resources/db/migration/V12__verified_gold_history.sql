-- Legacy market_prices remain intact. Only provider-verified rows enter this series.
CREATE TABLE gold_price_observations (
    ticker VARCHAR(32) NOT NULL REFERENCES assets(ticker),
    trade_date DATE NOT NULL,
    buy_price NUMERIC(19,4) NOT NULL CHECK (buy_price > 0),
    sell_price NUMERIC(19,4) NOT NULL CHECK (sell_price >= buy_price),
    observed_at TIMESTAMPTZ NOT NULL,
    source VARCHAR(64) NOT NULL,
    unit VARCHAR(16) NOT NULL DEFAULT 'VND_PER_CHI' CHECK (unit = 'VND_PER_CHI'),
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, trade_date)
);
CREATE TABLE gold_sync_state (
    provider VARCHAR(64) PRIMARY KEY,
    covered_until BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
