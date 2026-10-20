CREATE TABLE financial_goals (
 id BIGSERIAL PRIMARY KEY,
 user_id BIGINT NOT NULL REFERENCES users(id),
 title VARCHAR(120) NOT NULL,
 target_amount NUMERIC(19,4) NOT NULL CHECK(target_amount > 0),
 allocated_amount NUMERIC(19,4) NOT NULL CHECK(allocated_amount >= 0),
 monthly_contribution NUMERIC(19,4) NOT NULL CHECK(monthly_contribution >= 0),
 annual_rate NUMERIC(8,4) NOT NULL CHECK(annual_rate BETWEEN -50 AND 50),
 target_date DATE NOT NULL,
 version BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX idx_goals_user ON financial_goals(user_id);
CREATE EXTENSION IF NOT EXISTS unaccent;
ALTER TABLE vector_store ADD COLUMN search_tsv TSVECTOR;
UPDATE vector_store SET search_tsv=to_tsvector('simple',unaccent(content));
CREATE INDEX idx_vector_store_search ON vector_store USING gin(search_tsv);
