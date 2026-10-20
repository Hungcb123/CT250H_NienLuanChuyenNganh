package com.equifolio.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class GoldHistorySyncTest {
    final ObjectMapper mapper = new ObjectMapper();
    private String row(long epoch) {
        return """
            {"datetime":"%d","buy_1l":"139000000","sell_1l":"142000000",
             "buy_nhan1c":"138200000","sell_nhan1c":"141200000"}
            """.formatted(epoch);
    }
    @Test void parsesProviderTimeUnitsAndRejectsInvalidValues() throws Exception {
        long time = Instant.parse("2026-10-19T18:00:00Z").getEpochSecond();
        var rows = GoldHistorySync.parse(mapper.readTree("{\"results\":[" + row(time) + "]}"), 0, time);
        assertEquals(2, rows.size());
        assertEquals(LocalDate.of(2026,10,20), rows.getFirst().date());
        assertEquals(0, rows.getFirst().sell().compareTo(new java.math.BigDecimal("14200000")));
        assertEquals(0, rows.getLast().sell().compareTo(new java.math.BigDecimal("14120000")));
        assertThrows(IllegalArgumentException.class, () -> GoldHistorySync.parse(mapper.readTree("{\"results\":["+row(time)+"]}"), 0, time-1));
        assertThrows(IllegalArgumentException.class, () -> GoldHistorySync.parse(mapper.readTree("{\"results\":["+row(time).replace("139000000","0")+"]}"), 0, time));
    }
    @Test void bootstrapSplitsDenseRangesAndNextSyncUsesPersistedCursor() throws Exception {
        GoldPriceStore store = mock(GoldPriceStore.class);
        when(store.coveredUntil()).thenReturn(Optional.empty());
        var requests = new AtomicInteger();
        long start = Instant.parse("2026-01-01T00:00:00Z").getEpochSecond();
        var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0),0);
        server.createContext("/gold", exchange -> {
            requests.incrementAndGet();
            long from=0,to=Instant.now().getEpochSecond();
            String query=exchange.getRequestURI().getQuery();
            if(query!=null) for(String part:query.split("&")) {
                String[] pair=part.split("=");
                if(pair[0].equals("date_from"))from=Long.parseLong(pair[1]);else to=Long.parseLong(pair[1]);
            }
            // VnAppMob treats zero as an absent lower bound and returns only latest.
            if(query!=null && from==0) query=null;
            List<String> rows=new ArrayList<>();
            if(query==null) rows.add(row(start+199*86400));
            else for(int i=0;i<200;i++) { long time=start+i*86400; if(time>=from&&time<=to)rows.add(row(time)); }
            byte[] body=("{\"results\":["+String.join(",",rows)+"]}").getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200,body.length);exchange.getResponseBody().write(body);exchange.close();
        });
        server.start();
        try {
            var sync=new GoldHistorySync(store,mapper);
            ReflectionTestUtils.setField(sync,"key","test");
            ReflectionTestUtils.setField(sync,"url","http://127.0.0.1:"+server.getAddress().getPort()+"/gold");
            assertEquals("BACKFILL",sync.sync().get("mode"));
            assertTrue(requests.get()>2);
            @SuppressWarnings("unchecked") var saved=org.mockito.ArgumentCaptor.forClass((Class<List<GoldObservation>>)(Class<?>)List.class);
            verify(store).save(saved.capture(),anyLong());
            assertEquals(200,saved.getValue().stream().map(GoldObservation::date).distinct().count());
            reset(store);when(store.coveredUntil()).thenReturn(Optional.of(Instant.now().getEpochSecond()));
            requests.set(0);
            assertEquals("INCREMENTAL",sync.sync().get("mode"));
            assertEquals(2,requests.get());
        } finally {server.stop(0);}
    }
    @Test void networkFailureKeepsDatabaseAndCursorUntouched() {
        var store=mock(GoldPriceStore.class);
        when(store.coveredUntil()).thenReturn(Optional.of(123L));
        var sync=new GoldHistorySync(store,mapper);
        ReflectionTestUtils.setField(sync,"key","test");
        ReflectionTestUtils.setField(sync,"url","http://127.0.0.1:1/gold");
        assertEquals("STALE_DATABASE",sync.sync().get("status"));
        verify(store,never()).save(anyList(),anyLong());
    }
}
