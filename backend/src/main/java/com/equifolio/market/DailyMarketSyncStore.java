package com.equifolio.market;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import java.time.LocalDate;

@Repository
public class DailyMarketSyncStore {
    private final JdbcTemplate jdbc;
    public DailyMarketSyncStore(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    public boolean claim(LocalDate date, String market) {
        return jdbc.update("""
            INSERT INTO daily_market_sync_runs(sync_date,market,status) VALUES (?,?,'RUNNING')
            ON CONFLICT(sync_date,market) DO UPDATE SET status='RUNNING',
            attempts=daily_market_sync_runs.attempts+1,last_attempt_at=CURRENT_TIMESTAMP
            WHERE daily_market_sync_runs.status <> 'SUCCESS'
            AND daily_market_sync_runs.last_attempt_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes'
            """, date, market) == 1;
    }
    public void finish(LocalDate date, String market, boolean success, String detail) {
        jdbc.update("""
            UPDATE daily_market_sync_runs SET status=?,detail=?,
            completed_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END
            WHERE sync_date=? AND market=?
            """, success ? "SUCCESS" : "PENDING", detail, success, date, market);
    }
    public boolean stocksAvailable(LocalDate date) {
        Integer missing = jdbc.queryForObject("""
            SELECT count(*) FROM assets a WHERE a.asset_class='STOCK'
            AND NOT EXISTS(SELECT 1 FROM market_prices p WHERE p.ticker=a.ticker AND p.trade_date=?)
            """, Integer.class, date);
        return missing != null && missing == 0;
    }
    public boolean goldAvailable(LocalDate date) {
        Integer count = jdbc.queryForObject("""
            SELECT count(*) FROM gold_price_observations
            WHERE trade_date=? AND ticker IN ('GOLD_SJC','GOLD_RING_9999')
            """, Integer.class, date);
        return count != null && count == 2;
    }
}
