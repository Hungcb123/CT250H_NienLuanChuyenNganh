-- Reviewed history is embedded in the JAR; only completed live suffixes go here.
CREATE TABLE ml_onnx_market_bars (
    ticker varchar(16) NOT NULL CHECK (ticker IN ('VNINDEX', 'E1VFVN30')),
    session_date date NOT NULL,
    close double precision NOT NULL CHECK (close > 0),
    open double precision,
    high double precision,
    low double precision,
    volume double precision NOT NULL CHECK (volume >= 0),
    source_sha256 varchar(64) NOT NULL,
    received_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, session_date)
);
