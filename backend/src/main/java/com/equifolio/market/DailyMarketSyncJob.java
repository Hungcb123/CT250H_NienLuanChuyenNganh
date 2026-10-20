package com.equifolio.market;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import java.time.*;
import java.util.Map;

@Service
public class DailyMarketSyncJob {
    private static final Logger log = LoggerFactory.getLogger(DailyMarketSyncJob.class);
    private static final ZoneId ZONE = ZoneId.of("Asia/Ho_Chi_Minh");
    private static final LocalTime TARGET = LocalTime.of(14,50);
    private final DnseMarketDataService stocks;
    private final GoldHistorySync gold;
    private final DailyMarketSyncStore store;

    public DailyMarketSyncJob(DnseMarketDataService stocks, GoldHistorySync gold, DailyMarketSyncStore store) {
        this.stocks=stocks; this.gold=gold; this.store=store;
    }

    @Scheduled(cron="0 50 14 * * *", zone="Asia/Ho_Chi_Minh")
    public void scheduledDailySync() { runDue(ZonedDateTime.now(ZONE)); }

    // Also catches a missed 14:50 trigger after a backend restart.
    @Scheduled(fixedDelay=60000, initialDelay=60000)
    public void retryPendingSync() { runDue(ZonedDateTime.now(ZONE)); }

    synchronized void runDue(ZonedDateTime time) {
        var local=time.withZoneSameInstant(ZONE);
        if (local.toLocalTime().isBefore(TARGET) || local.toLocalTime().isAfter(LocalTime.of(23,45))) return;
        var date=local.toLocalDate();
        if (local.getDayOfWeek()!=DayOfWeek.SATURDAY && local.getDayOfWeek()!=DayOfWeek.SUNDAY) runStocks(date);
        runGold(date);
    }

    private void runStocks(LocalDate date) {
        if (!store.claim(date,"STOCKS")) return;
        try {
            Map<String,Object> report=stocks.syncAll();
            Object summary=report.get("vnindex");
            boolean indexToday=summary instanceof Map<?,?> index && date.toString().equals(index.get("latestDate"));
            boolean success=Boolean.TRUE.equals(report.get("vnindexUpdated")) && indexToday && store.stocksAvailable(date);
            store.finish(date,"STOCKS",success,success ? "Stored quotes for target date" : "Waiting for provider data for target date");
            log.info("[Daily Market Sync] STOCKS {} {}",date,success ? "SUCCESS" : "PENDING");
        } catch (Exception e) {
            store.finish(date,"STOCKS",false,"Sync failed; retry after 15 minutes");
            log.warn("[Daily Market Sync] STOCKS {} failed ({})",date,e.getClass().getSimpleName());
        }
    }

    private void runGold(LocalDate date) {
        if (!store.claim(date,"GOLD")) return;
        try {
            var report=gold.sync();
            boolean success="SYNCED".equals(report.get("status")) && store.goldAvailable(date);
            store.finish(date,"GOLD",success,success ? "Stored observations for target date" : "Waiting for verified provider observations");
            log.info("[Daily Market Sync] GOLD {} {}",date,success ? "SUCCESS" : "PENDING");
        } catch (Exception e) {
            store.finish(date,"GOLD",false,"Sync failed; retry after 15 minutes");
            log.warn("[Daily Market Sync] GOLD {} failed ({})",date,e.getClass().getSimpleName());
        }
    }
}
