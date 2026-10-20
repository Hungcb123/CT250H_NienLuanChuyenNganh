package com.equifolio.ledger;

import com.equifolio.market.BenchmarkStore;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.*;
import org.springframework.transaction.support.TransactionTemplate;
import java.math.BigDecimal;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

@EnabledIfEnvironmentVariable(named="EQUIFOLIO_GOLD_TEST_URL",matches="jdbc:postgresql:.*")
class PreparedPerformanceDatabaseTest {
    @Test void preparedReadOnlyPerformanceInvalidationRestatementAndSharedBenchmark() throws Exception {
        String url=System.getenv("EQUIFOLIO_GOLD_TEST_URL"),user=System.getenv().getOrDefault("DB_USER","postgres"),password=System.getenv().getOrDefault("DB_PASSWORD","postgres");
        var admin=new JdbcTemplate(new DriverManagerDataSource(url,user,password));
        String schema="performance_validation_"+UUID.randomUUID().toString().replace("-","");
        admin.execute("CREATE SCHEMA "+schema);
        try {
            var ds=new DriverManagerDataSource(url+(url.contains("?")?"&":"?")+"currentSchema="+schema,user,password);
            var jdbc=new JdbcTemplate(ds);var manager=new DataSourceTransactionManager(ds);var tx=new TransactionTemplate(manager);
            fixture(jdbc);
            jdbc.execute(Files.readString(Path.of("src/main/resources/db/migration/V14__prepared_portfolio_performance.sql")));
            var mapper=new ObjectMapper();
            var worker=new PreparedPerformanceWorker(jdbc,mapper,manager);
            var reader=new PreparedPerformanceReader(jdbc,mapper);
            var benchmark=new BenchmarkStore(jdbc,mapper);
            LocalDate today=LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh")),a=today.minusDays(2),b=today.minusDays(1);
            jdbc.update("INSERT INTO users VALUES(1,'alice','a@test'),(2,'bob','b@test')");
            jdbc.update("INSERT INTO assets VALUES('VND','CASH'),('HPG','STOCK')");
            jdbc.update("INSERT INTO accounts VALUES(1,1,'VND_WALLET','VND',220),(2,1,'EQUITY_CAPITAL','VND',-200),(3,1,'INTEREST_INCOME','VND',-20),(4,2,'ASSET_HPG','HPG',1),(5,2,'EQUITY_CAPITAL','VND',-50)");
            transaction(jdbc,1,1,"CAPITAL_INJECTION",a);transaction(jdbc,2,1,"CAPITAL_INJECTION",b);transaction(jdbc,3,1,"DIVIDEND_CASH",today);transaction(jdbc,4,2,"CAPITAL_INJECTION",a);
            jdbc.update("INSERT INTO entries VALUES(1,1,1,100),(2,1,2,-100),(3,2,1,100),(4,2,2,-100),(5,3,1,20),(6,3,3,-20),(7,4,4,1),(8,4,5,-50)");
            jdbc.update("INSERT INTO market_prices VALUES('HPG',?,50,now()),('HPG',?,50,now()),('HPG',?,55,now())",a,b,today);
            snapshot(jdbc,1,a,100,0,100);snapshot(jdbc,1,b,200,0,200);
            snapshot(jdbc,2,a,50,50,0);snapshot(jdbc,2,b,50,50,0);
            tx.execute(s->{benchmark.publish(List.of(bar(a,100),bar(b,101),bar(today,102)));return null;});
            assertEquals("PREPARING",reader.history(1L,"ALL").getStatus());
            worker.runPending();
            assertEquals(2,jdbc.queryForObject("SELECT count(*) FROM performance_head",Integer.class),"Both accounts must publish");
            var history=reader.history(1L,"ALL");
            assertEquals(new BigDecimal("10.00"),history.getPortfolioReturnPercent());
            assertEquals(new BigDecimal("2.00"),history.getVniReturnPercent());
            assertEquals(new BigDecimal("8.00"),history.getAlphaPercent());
            assertEquals(3,history.getPoints().size());
            assertEquals(3,jdbc.queryForObject("SELECT count(*) FROM benchmark_daily",Integer.class),"Shared benchmark is not duplicated per user");
            assertNotEquals(history.getCurrentNav(),reader.history(2L,"ALL").getCurrentNav(),"User isolation");
            var before=fingerprint(jdbc);
            var readManager=new DataSourceTransactionManager(ds);readManager.setEnforceReadOnly(true);
            var readOnly=new TransactionTemplate(readManager);readOnly.setReadOnly(true);
            readOnly.execute(s->{reader.history(1L,"1Y");reader.history(1L,"YTD");reader.risk(1L);return null;});
            assertEquals(before,fingerprint(jdbc),"GET readers must not write snapshots, queues or cache");
            String oldVersion=history.getDataVersion();

            // Withdrawal changes today's NAV but must not become an investment loss.
            transaction(jdbc,5,1,"CAPITAL_WITHDRAWAL",today);
            jdbc.update("INSERT INTO entries VALUES(9,5,1,-50),(10,5,2,50)");
            jdbc.update("UPDATE accounts SET balance=170 WHERE id=1");jdbc.update("UPDATE accounts SET balance=-150 WHERE id=2");
            var stale=reader.history(1L,"ALL");
            assertTrue(stale.getUpdating());assertEquals(oldVersion,stale.getDataVersion());assertEquals(new BigDecimal("220.000000"),stale.getCurrentNav());
            worker.runPending();
            var fresh=reader.history(1L,"ALL");
            assertNotEquals(oldVersion,fresh.getDataVersion());
            assertEquals(new BigDecimal("10.00"),fresh.getPortfolioReturnPercent());assertEquals(0,fresh.getCurrentNav().compareTo(new BigDecimal("170")));

            // Backdating that withdrawal rebuilds the affected historical NAV and growth.
            jdbc.update("UPDATE transactions SET created_at=? WHERE id=5",b.atTime(12,0).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toOffsetDateTime());
            worker.runPending();
            fresh=reader.history(1L,"ALL");
            assertEquals(new BigDecimal("13.33"),fresh.getPortfolioReturnPercent());
            assertEquals(0,fresh.getPoints().get(1).getNav().compareTo(new BigDecimal("150")));

            // Historical price correction is applied to observed holdings, not today's holdings.
            jdbc.update("UPDATE market_prices SET price=40 WHERE ticker='HPG' AND trade_date=?",a);
            worker.runPending();
            assertEquals(new BigDecimal("37.50"),reader.history(2L,"ALL").getPortfolioReturnPercent());

            // A new shared benchmark must not leak into the previous published generation.
            var old=reader.history(1L,"ALL");
            tx.execute(s->{benchmark.publish(List.of(bar(a,100),bar(b,101),bar(today,104)));return null;});
            assertEquals(old.getVniReturnPercent(),reader.history(1L,"ALL").getVniReturnPercent());
            worker.runPending();
            assertEquals(new BigDecimal("4.00"),reader.history(1L,"ALL").getVniReturnPercent());

            // Daily price success triggers closing; there is no separate 15:05 timer.
            jdbc.update("INSERT INTO daily_market_sync_runs VALUES(?,'STOCKS','SUCCESS'),(?,'GOLD','SUCCESS')",today,today);
            worker.runPending();
            assertFalse(reader.history(1L,"ALL").getProvisional());
            assertEquals("FINAL",jdbc.queryForObject("SELECT valuation_status FROM portfolio_snapshots WHERE user_id=1 AND snapshot_date=?",String.class,today));

            // Missing prices retain the previous complete generation, and retry is queued.
            var complete=reader.history(2L,"ALL");
            jdbc.update("DELETE FROM market_prices WHERE ticker='HPG'");
            worker.runPending();
            assertEquals(complete.getDataVersion(),reader.history(2L,"ALL").getDataVersion());
            assertTrue(reader.history(2L,"ALL").getUpdating());
            assertNotNull(jdbc.queryForObject("SELECT last_error FROM performance_dirty WHERE user_id=2",String.class));
        } finally {admin.execute("DROP SCHEMA "+schema+" CASCADE");}
    }
    static Map<String,Object> bar(LocalDate d,double close) {return Map.of("date",d.toString(),"close",close);}
    static void transaction(JdbcTemplate jdbc,long id,long uid,String type,LocalDate date) {
        jdbc.update("INSERT INTO transactions VALUES(?,?,?,'POSTED',?)",id,uid,type,date.atTime(12,0).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toOffsetDateTime());
    }
    static void snapshot(JdbcTemplate jdbc,long uid,LocalDate day,int nav,int stock,int cash) {
        jdbc.update("INSERT INTO portfolio_snapshots(user_id,snapshot_date,total_nav,stock_value,cash_value,snapshot_source) VALUES(?,?,?,?,?,'OBSERVED')",uid,day,nav,stock,cash);
    }
    static String fingerprint(JdbcTemplate jdbc) {
        return jdbc.queryForObject("""
            SELECT (SELECT count(*) FROM portfolio_snapshots)::text || ':' || (SELECT sum(total_nav) FROM portfolio_snapshots)::text
             || ':' || (SELECT count(*) FROM performance_dirty)::text || ':' || (SELECT sum(generation) FROM performance_head)::text
            """,String.class);
    }
    static void fixture(JdbcTemplate jdbc) {
        jdbc.execute("CREATE TABLE users(id bigint PRIMARY KEY,username text,email text)");
        jdbc.execute("CREATE TABLE assets(ticker text PRIMARY KEY,asset_class text)");
        jdbc.execute("CREATE TABLE accounts(id bigint PRIMARY KEY,user_id bigint REFERENCES users,account_code text,asset_type text,balance numeric)");
        jdbc.execute("CREATE TABLE transactions(id bigint PRIMARY KEY,user_id bigint REFERENCES users,type text,status text,created_at timestamptz)");
        jdbc.execute("CREATE TABLE entries(id bigint PRIMARY KEY,transaction_id bigint REFERENCES transactions ON DELETE CASCADE,account_id bigint REFERENCES accounts,amount numeric)");
        jdbc.execute("CREATE TABLE market_prices(ticker text,trade_date date,price numeric,updated_at timestamptz,PRIMARY KEY(ticker,trade_date))");
        jdbc.execute("""
            CREATE TABLE portfolio_snapshots(id bigserial PRIMARY KEY,user_id bigint REFERENCES users,snapshot_date date,
             total_nav numeric NOT NULL,stock_value numeric DEFAULT 0,gold_value numeric DEFAULT 0,savings_value numeric DEFAULT 0,
             cash_value numeric DEFAULT 0,vnindex_value numeric DEFAULT 0,snapshot_source text,created_at timestamptz DEFAULT now(),
             UNIQUE(user_id,snapshot_date))
            """);
        jdbc.execute("CREATE TABLE daily_market_sync_runs(sync_date date,market text,status text,PRIMARY KEY(sync_date,market))");
        jdbc.execute("CREATE TABLE macro_indicators(indicator_code text,indicator_value numeric,recorded_date date)");
    }
}
