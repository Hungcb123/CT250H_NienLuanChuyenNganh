CREATE SEQUENCE performance_input_version;
CREATE SEQUENCE performance_generation;
CREATE SEQUENCE benchmark_generation;

CREATE TABLE benchmark_versions (
    generation BIGINT PRIMARY KEY,
    checksum VARCHAR(64) NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE benchmark_daily (
    generation BIGINT NOT NULL REFERENCES benchmark_versions(generation) ON DELETE CASCADE,
    price_date DATE NOT NULL,
    close NUMERIC(19,6) NOT NULL CHECK(close>0),
    PRIMARY KEY(generation,price_date)
);
CREATE TABLE benchmark_head (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(singleton),
    generation BIGINT NOT NULL REFERENCES benchmark_versions(generation)
);
CREATE TABLE performance_dirty (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    input_version BIGINT NOT NULL DEFAULT nextval('performance_input_version'),
    dirty_from DATE NOT NULL,
    revalue_from DATE,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retry_after TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error VARCHAR(255)
);
CREATE TABLE performance_head (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    generation BIGINT NOT NULL,
    input_version BIGINT NOT NULL,
    benchmark_generation BIGINT REFERENCES benchmark_versions(generation),
    formula_version INTEGER NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    as_of_date DATE NOT NULL,
    price_as_of DATE,
    provisional BOOLEAN NOT NULL,
    data_kind VARCHAR(16) NOT NULL,
    risk_payload JSONB NOT NULL
);
CREATE TABLE performance_daily (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generation BIGINT NOT NULL,
    snapshot_date DATE NOT NULL,
    nav NUMERIC(24,6) NOT NULL,
    stock NUMERIC(24,6) NOT NULL,
    gold NUMERIC(24,6) NOT NULL,
    savings NUMERIC(24,6) NOT NULL,
    cash NUMERIC(24,6) NOT NULL,
    growth_index NUMERIC(32,16),
    external_flow NUMERIC(24,6) NOT NULL,
    PRIMARY KEY(user_id,generation,snapshot_date)
);
ALTER TABLE portfolio_snapshots ADD COLUMN valuation_status VARCHAR(16) NOT NULL DEFAULT 'LEGACY';
ALTER TABLE portfolio_snapshots ADD COLUMN price_as_of DATE;

CREATE FUNCTION mark_performance_dirty(uid BIGINT, since_date DATE, revalue BOOLEAN) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
 IF uid IS NULL OR current_setting('equifolio.performance_worker',true)='on' THEN RETURN; END IF;
 INSERT INTO performance_dirty(user_id,dirty_from,revalue_from)
 SELECT uid,since_date,CASE WHEN revalue THEN since_date END WHERE EXISTS(SELECT 1 FROM users WHERE id=uid)
 ON CONFLICT(user_id) DO UPDATE SET
 input_version=nextval('performance_input_version'),
 dirty_from=LEAST(performance_dirty.dirty_from,EXCLUDED.dirty_from),
 revalue_from=LEAST(performance_dirty.revalue_from,EXCLUDED.revalue_from),
 requested_at=now(),retry_after=now(),last_error=NULL;
END $$;

CREATE FUNCTION invalidate_performance_row() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE row_data JSONB; uid BIGINT; day DATE;
BEGIN
 IF current_setting('equifolio.performance_worker',true)='on' THEN RETURN NULL; END IF;
 FOR row_data IN SELECT to_jsonb(OLD) WHERE TG_OP<>'INSERT' UNION ALL SELECT to_jsonb(NEW) WHERE TG_OP<>'DELETE'
 LOOP
  IF TG_TABLE_NAME='users' THEN
   uid=(row_data->>'id')::bigint;day=(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
  ELSIF TG_TABLE_NAME='entries' THEN
   SELECT user_id,(created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date INTO uid,day
   FROM transactions WHERE id=(row_data->>'transaction_id')::bigint;
  ELSIF TG_TABLE_NAME='transactions' THEN
   uid=(row_data->>'user_id')::bigint;day=((row_data->>'created_at')::timestamptz AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
  ELSIF TG_TABLE_NAME='portfolio_snapshots' THEN
   uid=(row_data->>'user_id')::bigint;day=(row_data->>'snapshot_date')::date;
  ELSE
   uid=(row_data->>'user_id')::bigint;day=(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
  END IF;
  PERFORM mark_performance_dirty(uid,day,TG_TABLE_NAME IN ('transactions','entries','accounts'));
 END LOOP;
 RETURN NULL;
END $$;
CREATE TRIGGER performance_accounts_changed AFTER INSERT OR UPDATE OR DELETE ON accounts FOR EACH ROW EXECUTE FUNCTION invalidate_performance_row();
CREATE TRIGGER performance_transactions_changed AFTER INSERT OR UPDATE OR DELETE ON transactions FOR EACH ROW EXECUTE FUNCTION invalidate_performance_row();
CREATE TRIGGER performance_entries_changed AFTER INSERT OR UPDATE OR DELETE ON entries FOR EACH ROW EXECUTE FUNCTION invalidate_performance_row();
CREATE TRIGGER performance_snapshots_changed AFTER INSERT OR UPDATE OR DELETE ON portfolio_snapshots FOR EACH ROW EXECUTE FUNCTION invalidate_performance_row();
CREATE TRIGGER performance_users_created AFTER INSERT ON users FOR EACH ROW EXECUTE FUNCTION invalidate_performance_row();

CREATE FUNCTION invalidate_performance_price() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE holder BIGINT; ticker_value TEXT; day DATE;
BEGIN
 IF TG_OP='UPDATE' AND OLD.price IS NOT DISTINCT FROM NEW.price AND OLD.trade_date=NEW.trade_date AND OLD.ticker=NEW.ticker THEN RETURN NULL; END IF;
 IF TG_OP<>'INSERT' THEN
  FOR holder IN SELECT DISTINCT user_id FROM accounts WHERE asset_type=OLD.ticker LOOP
   PERFORM mark_performance_dirty(holder,OLD.trade_date,TRUE);
  END LOOP;
 END IF;
 IF TG_OP<>'DELETE' THEN
  FOR holder IN SELECT DISTINCT user_id FROM accounts WHERE asset_type=NEW.ticker LOOP
   PERFORM mark_performance_dirty(holder,NEW.trade_date,TRUE);
  END LOOP;
 END IF;
 RETURN NULL;
END $$;
CREATE TRIGGER performance_prices_changed AFTER INSERT OR UPDATE OR DELETE ON market_prices FOR EACH ROW EXECUTE FUNCTION invalidate_performance_price();

CREATE FUNCTION invalidate_performance_close() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.status='SUCCESS' AND (TG_OP='INSERT' OR OLD.status IS DISTINCT FROM NEW.status) AND
 (SELECT count(*) FROM daily_market_sync_runs WHERE sync_date=NEW.sync_date AND status='SUCCESS' AND market IN ('GOLD','STOCKS'))=2 THEN
  INSERT INTO performance_dirty(user_id,dirty_from)
  SELECT id,NEW.sync_date FROM users
  ON CONFLICT(user_id) DO UPDATE SET input_version=nextval('performance_input_version'),
    dirty_from=LEAST(performance_dirty.dirty_from,EXCLUDED.dirty_from),requested_at=now(),retry_after=now();
 END IF;
 RETURN NULL;
END $$;
CREATE TRIGGER performance_after_close AFTER INSERT OR UPDATE ON daily_market_sync_runs FOR EACH ROW EXECUTE FUNCTION invalidate_performance_close();
INSERT INTO performance_dirty(user_id,dirty_from) SELECT id,DATE '1970-01-01' FROM users;
CREATE INDEX performance_dirty_due ON performance_dirty(retry_after,requested_at);

CREATE FUNCTION invalidate_performance_rf() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
 IF (TG_OP<>'DELETE' AND NEW.indicator_code='RF_INTERBANK_RATE') OR
    (TG_OP<>'INSERT' AND OLD.indicator_code='RF_INTERBANK_RATE') THEN
  IF TG_OP='UPDATE' AND OLD.indicator_value IS NOT DISTINCT FROM NEW.indicator_value
      AND OLD.indicator_code=NEW.indicator_code THEN RETURN NULL; END IF;
  INSERT INTO performance_dirty(user_id,dirty_from)
  SELECT id,(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date FROM users
  ON CONFLICT(user_id) DO UPDATE SET input_version=nextval('performance_input_version'),
    requested_at=now(),retry_after=now(),last_error=NULL;
 END IF;
 RETURN NULL;
END $$;
CREATE TRIGGER performance_rf_changed AFTER INSERT OR UPDATE OR DELETE ON macro_indicators FOR EACH ROW EXECUTE FUNCTION invalidate_performance_rf();
