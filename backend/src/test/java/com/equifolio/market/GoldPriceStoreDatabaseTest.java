package com.equifolio.market;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import java.nio.file.*;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

@EnabledIfEnvironmentVariable(named="EQUIFOLIO_GOLD_TEST_URL",matches="jdbc:postgresql:.*")
class GoldPriceStoreDatabaseTest {
    @Test void provenanceUpsertCursorAndReadOnlyQueries() throws Exception {
        String url=System.getenv("EQUIFOLIO_GOLD_TEST_URL");
        String user=System.getenv().getOrDefault("DB_USER","postgres");
        String password=System.getenv().getOrDefault("DB_PASSWORD","postgres");
        var admin=new JdbcTemplate(new DriverManagerDataSource(url,user,password));
        String schema="gold_validation_"+UUID.randomUUID().toString().replace("-","");
        admin.execute("CREATE SCHEMA "+schema);
        try {
            var source=new DriverManagerDataSource(url+(url.contains("?")?"&":"?")+"currentSchema="+schema,user,password);
            var jdbc=new JdbcTemplate(source);
            jdbc.execute("CREATE TABLE assets(ticker varchar(32) PRIMARY KEY)");
            jdbc.update("INSERT INTO assets VALUES ('GOLD_SJC'),('GOLD_RING_9999')");
            jdbc.execute("CREATE TABLE market_prices(ticker varchar(32),trade_date date,price numeric,updated_at timestamptz, UNIQUE(ticker,trade_date))");
            jdbc.execute(Files.readString(Path.of("src/main/resources/db/migration/V12__verified_gold_history.sql")));
            jdbc.update("INSERT INTO market_prices VALUES('GOLD_SJC','2025-01-01',8400000,now())");
            var store=new GoldPriceStore(jdbc);
            var tx=new TransactionTemplate(new DataSourceTransactionManager(source));
            var old=new GoldObservation("GOLD_SJC",new BigDecimal("13900000"),new BigDecimal("14200000"),Instant.parse("2026-10-19T01:00:00Z"));
            var latest=new GoldObservation("GOLD_SJC",new BigDecimal("14000000"),new BigDecimal("14300000"),Instant.parse("2026-10-20T01:00:00Z"));
            tx.execute(s->{store.save(List.of(old,latest),500L);return null;});
            tx.execute(s->{store.save(List.of(old,latest),500L);return null;});
            assertEquals(2,store.history("GOLD_SJC").size());
            assertEquals(3,jdbc.queryForObject("SELECT count(*) FROM market_prices",Integer.class));
            assertEquals(500L,new GoldPriceStore(jdbc).coveredUntil().orElseThrow());
            var stale=new GoldObservation("GOLD_SJC",BigDecimal.ONE,BigDecimal.TEN,Instant.parse("2026-10-20T00:00:00Z"));
            tx.execute(s->{store.save(List.of(stale),400L);return null;});
            assertEquals(0,store.latest().getFirst().sellPrice().compareTo(latest.sell()));
            assertEquals(LocalDate.of(2026,10,20),store.latest().getFirst().tradeDate());
            assertEquals(100000.,store.latest().getFirst().changeValue());
            var before=jdbc.queryForObject("SELECT count(*) FROM gold_price_observations",Integer.class);
            store.latest();store.latest();store.history("GOLD_SJC");
            assertEquals(before,jdbc.queryForObject("SELECT count(*) FROM gold_price_observations",Integer.class));
            assertThrows(Exception.class,()->tx.execute(s->{store.save(List.of(new GoldObservation("BAD",BigDecimal.ONE,BigDecimal.TEN,Instant.now())),999L);return null;}));
            assertEquals(500L,store.coveredUntil().orElseThrow());
        } finally {admin.execute("DROP SCHEMA "+schema+" CASCADE");}
    }
}
