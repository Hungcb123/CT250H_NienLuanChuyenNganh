package com.equifolio.market;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import java.nio.file.*;
import java.time.LocalDate;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;

@EnabledIfEnvironmentVariable(named="EQUIFOLIO_GOLD_TEST_URL",matches="jdbc:postgresql:.*")
class DailyMarketSyncStoreDatabaseTest {
    @Test void persistedClaimsRetryLeaseAndSuccessSurviveNewInstances() throws Exception {
        String url=System.getenv("EQUIFOLIO_GOLD_TEST_URL");
        String user=System.getenv().getOrDefault("DB_USER","postgres"),password=System.getenv().getOrDefault("DB_PASSWORD","postgres");
        var admin=new JdbcTemplate(new DriverManagerDataSource(url,user,password));
        String schema="daily_sync_validation_"+UUID.randomUUID().toString().replace("-","");
        admin.execute("CREATE SCHEMA "+schema);
        try {
            var jdbc=new JdbcTemplate(new DriverManagerDataSource(url+(url.contains("?")?"&":"?")+"currentSchema="+schema,user,password));
            jdbc.execute(Files.readString(Path.of("src/main/resources/db/migration/V13__daily_market_sync_runs.sql")));
            var store=new DailyMarketSyncStore(jdbc);
            var date=LocalDate.of(2026,10,20);
            assertTrue(store.claim(date,"STOCKS"));
            assertFalse(new DailyMarketSyncStore(jdbc).claim(date,"STOCKS"));
            store.finish(date,"STOCKS",false,"provider pending");
            assertFalse(store.claim(date,"STOCKS"));
            jdbc.update("UPDATE daily_market_sync_runs SET last_attempt_at=now()-interval '16 minutes'");
            assertTrue(store.claim(date,"STOCKS"));
            assertEquals(2,jdbc.queryForObject("SELECT attempts FROM daily_market_sync_runs",Integer.class));
            store.finish(date,"STOCKS",true,"done");
            jdbc.update("UPDATE daily_market_sync_runs SET last_attempt_at=now()-interval '1 hour'");
            assertFalse(new DailyMarketSyncStore(jdbc).claim(date,"STOCKS"));
            assertTrue(store.claim(date,"GOLD"));
            assertTrue(store.claim(date.plusDays(1),"STOCKS"));
        } finally {admin.execute("DROP SCHEMA "+schema+" CASCADE");}
    }
}
