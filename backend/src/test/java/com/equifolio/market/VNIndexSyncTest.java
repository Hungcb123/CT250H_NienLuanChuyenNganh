package com.equifolio.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.http.*;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class VNIndexSyncTest {
    @Test void summaryAndHistoryPublishTogetherAndFailureCannotClaimSuccessfulIndexSync() throws Exception {
        var assets=mock(AssetRepository.class); var prices=mock(MarketPriceRepository.class);
        var service=new DnseMarketDataService(assets,prices,new ObjectMapper());
        var http=mock(HttpClient.class);ReflectionTestUtils.setField(service,"httpClient",http);
        var response=mock(HttpResponse.class);
        List<Long> times=new ArrayList<>(); List<Double> closes=new ArrayList<>();List<Long> volumes=new ArrayList<>();
        LocalDate start=LocalDate.of(2026,10,1);
        for(int i=0;i<60;i++) {times.add(start.plusDays(i).atStartOfDay(ZoneId.of("Asia/Ho_Chi_Minh")).toEpochSecond());closes.add(1600.+i);volumes.add(1000000L+i);}
        when(response.statusCode()).thenReturn(200);
        when(response.body()).thenReturn(new ObjectMapper().writeValueAsString(Map.of("t",times,"c",closes,"v",volumes)));
        doReturn(response).when(http).send(any(HttpRequest.class),any(HttpResponse.BodyHandler.class));
        var report=service.syncAll();assertEquals(true,report.get("vnindexUpdated"));
        var summary=service.getVNIndexSummary();
        assertEquals(1659.,summary.get("currentPoints"));
        var history=(List<Map<String,Object>>)summary.get("history");
        assertEquals(60,history.size());assertEquals(summary.get("currentPoints"),history.getLast().get("close"));
        assertEquals(summary.get("ma20"),history.getLast().get("ma20"));
        assertNull(history.getFirst().get("ma20"));
        when(response.statusCode()).thenReturn(503);
        assertEquals(false,service.syncAll().get("vnindexUpdated"));
        assertEquals(summary,service.getVNIndexSummary());
    }

    @Test void missingLiveIndexNeverReturnsTheHardcodedOctoberEighthPrice() {
        var dnse=mock(DnseMarketDataService.class);when(dnse.getVNIndexSummary()).thenReturn(Map.of());
        var service=new MarketService(mock(AssetRepository.class),mock(MarketPriceRepository.class),dnse);
        assertThrows(IllegalStateException.class,service::getVNIndexSummary);
    }
}
