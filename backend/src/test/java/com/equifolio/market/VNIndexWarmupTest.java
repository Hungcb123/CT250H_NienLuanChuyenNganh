package com.equifolio.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import java.net.http.*;
import java.time.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class VNIndexWarmupTest {
    @Test void indexRequestIncludesWarmupBeforeOneYearVisibleRange() throws Exception {
        var assets=mock(AssetRepository.class);var prices=mock(MarketPriceRepository.class);
        var mapper=new ObjectMapper();
        var service=new DnseMarketDataService(assets,prices,mapper);
        var http=mock(HttpClient.class);ReflectionTestUtils.setField(service,"httpClient",http);
        var response=mock(HttpResponse.class);
        when(response.statusCode()).thenReturn(200);
        List<Long> times=new ArrayList<>();List<Double> closes=new ArrayList<>();
        var today=LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh"));
        for(int i=899;i>=0;i--) {
            var day=today.minusDays(i);
            if(day.getDayOfWeek()==DayOfWeek.SATURDAY||day.getDayOfWeek()==DayOfWeek.SUNDAY)continue;
            times.add(day.atStartOfDay(ZoneId.of("Asia/Ho_Chi_Minh")).toEpochSecond());closes.add(1000.+times.size());
        }
        when(response.body()).thenReturn(mapper.writeValueAsString(Map.of("t",times,"c",closes)));
        doAnswer(inv->{
            HttpRequest req=inv.getArgument(0);
            Map<String,Long> params=new HashMap<>();
            for(String pair:req.uri().getQuery().split("&")) {
                String[] kv=pair.split("=");if(kv[0].equals("from")||kv[0].equals("to"))params.put(kv[0],Long.parseLong(kv[1]));
            }
            assertTrue(params.get("to")-params.get("from")>=900L*86400);
            return response;
        }).when(http).send(any(HttpRequest.class),any(HttpResponse.BodyHandler.class));
        assertEquals(true,service.syncAll().get("vnindexUpdated"));
        @SuppressWarnings("unchecked")
        var history=(List<Map<String,Object>>)service.getVNIndexSummary().get("history");
        var cutoff=today.minusYears(1).toString();
        int first=0;while(history.get(first).get("date").toString().compareTo(cutoff)<0)first++;
        assertTrue(first>=199,"First visible point must have 199 earlier trading sessions");
        assertTrue(history.size()-first>240);
    }
}
