package com.equifolio.market;

import org.junit.jupiter.api.Test;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.scheduling.support.CronExpression;
import java.time.*;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class DailyMarketSyncJobTest {
    final DnseMarketDataService stocks=mock(DnseMarketDataService.class);
    final GoldHistorySync gold=mock(GoldHistorySync.class);
    final DailyMarketSyncStore store=mock(DailyMarketSyncStore.class);
    final DailyMarketSyncJob job=new DailyMarketSyncJob(stocks,gold,store);
    final ZoneId zone=ZoneId.of("Asia/Ho_Chi_Minh");
    final LocalDate date=LocalDate.of(2026,10,20);
    void claims() { when(store.claim(any(),anyString())).thenReturn(true); }
    void valid() {
        claims();
        when(stocks.syncAll()).thenReturn(Map.of("vnindexUpdated",true,"vnindex",Map.of("latestDate",date.toString())));
        when(gold.sync()).thenReturn(Map.of("status","SYNCED"));
        when(store.stocksAvailable(date)).thenReturn(true);
        when(store.goldAvailable(date)).thenReturn(true);
    }
    @Test void cronIsExactly1450VietnamTime() throws Exception {
        var annotation=DailyMarketSyncJob.class.getMethod("scheduledDailySync").getAnnotation(Scheduled.class);
        assertEquals("Asia/Ho_Chi_Minh",annotation.zone());
        var next=CronExpression.parse(annotation.cron()).next(date.atTime(14,49).atZone(zone));
        assertEquals(date.atTime(14,50).atZone(zone),next);
    }
    @Test void noRunBeforeTarget() {
        job.runDue(date.atTime(14,49,59).atZone(zone));
        verifyNoInteractions(store,stocks,gold);
    }
    @Test void targetRunsBothMarketsAndPersistsSuccess() {
        valid();job.runDue(date.atTime(7,50).atZone(ZoneId.of("UTC")));
        verify(store).finish(eq(date),eq("STOCKS"),eq(true),anyString());
        verify(store).finish(eq(date),eq("GOLD"),eq(true),anyString());
    }
    @Test void oldPricesRemainPendingRatherThanSuccessful() {
        claims();
        when(stocks.syncAll()).thenReturn(Map.of("vnindexUpdated",true,"vnindex",Map.of("latestDate",date.minusDays(1).toString())));
        when(gold.sync()).thenReturn(Map.of("status","STALE_DATABASE"));
        job.runDue(date.atTime(14,50).atZone(zone));
        verify(store).finish(eq(date),eq("STOCKS"),eq(false),anyString());
        verify(store).finish(eq(date),eq("GOLD"),eq(false),anyString());
    }
    @Test void backendRestartAfterTargetCatchesUp() {
        valid();job.runDue(date.atTime(16,0).atZone(zone));
        verify(stocks).syncAll();verify(gold).sync();
    }
    @Test void completedOrRecentlyClaimedRunDoesNotFetchAgain() {
        job.runDue(date.atTime(15,0).atZone(zone));
        verifyNoInteractions(stocks,gold);
    }
    @Test void stockFailureDoesNotPreventGoldSync() {
        valid();when(stocks.syncAll()).thenThrow(new IllegalStateException("network"));
        job.runDue(date.atTime(14,50).atZone(zone));
        verify(store).finish(eq(date),eq("STOCKS"),eq(false),anyString());
        verify(gold).sync();
    }
    @Test void weekendRunsOnlyGold() {
        claims();when(gold.sync()).thenReturn(Map.of("status","SYNCED"));
        job.runDue(LocalDate.of(2026,10,24).atTime(14,50).atZone(zone));
        verifyNoInteractions(stocks);
        verify(gold).sync();
    }
}
