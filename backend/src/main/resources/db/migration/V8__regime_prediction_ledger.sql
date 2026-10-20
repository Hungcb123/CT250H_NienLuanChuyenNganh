-- Separate from portfolio transactions: one serialized state stream per policy.
CREATE TABLE ml_regime_streams (
    stream_key varchar(64) PRIMARY KEY,
    asset varchar(32) NOT NULL,
    mode varchar(16) NOT NULL CHECK (mode IN ('live', 'historical')),
    policy jsonb NOT NULL,
    last_session date,
    state jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ml_regime_predictions (
    stream_key varchar(64) NOT NULL REFERENCES ml_regime_streams(stream_key),
    session_date date NOT NULL,
    previous_market_session date,
    input_sha256 varchar(64) NOT NULL,
    bundle_sha256 varchar(64) NOT NULL,
    raw_scores jsonb NOT NULL CHECK (jsonb_array_length(raw_scores) = 3),
    ema_scores jsonb NOT NULL CHECK (jsonb_array_length(ema_scores) = 3),
    final_scores jsonb NOT NULL CHECK (jsonb_array_length(final_scores) = 3),
    response jsonb NOT NULL,
    published_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (stream_key, session_date)
);

CREATE INDEX ml_regime_predictions_session_idx ON ml_regime_predictions (session_date DESC);
