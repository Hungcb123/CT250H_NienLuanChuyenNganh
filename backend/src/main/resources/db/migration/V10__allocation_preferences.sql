CREATE TABLE allocation_preferences (
 user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 mode VARCHAR(3) NOT NULL CHECK (mode IN ('SAA','TAA')),
 horizon_sessions INTEGER NOT NULL CHECK (horizon_sessions IN (20,60,120)),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ml_long_horizon_predictions (
 policy TEXT NOT NULL,
 horizon_sessions INTEGER NOT NULL CHECK (horizon_sessions IN (60,120)),
 session_date DATE NOT NULL,
 response JSONB NOT NULL,
 published_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(policy,horizon_sessions,session_date)
);
