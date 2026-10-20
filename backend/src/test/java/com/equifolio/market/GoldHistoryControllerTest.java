package com.equifolio.market;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class GoldHistoryControllerTest {
    @Test void returnsStoredGoldPricesInVndPerChi() {
        var repo = mock(GoldPriceStore.class);
        when(repo.history("GOLD_SJC")).thenReturn(List.of(
                new GoldPriceStore.Bar(LocalDate.of(2026, 10, 20), new BigDecimal("14300000"))));
        var result = new GoldHistoryController(repo).history("GOLD_SJC");
        assertEquals(new BigDecimal("14300000"), result.getData().getFirst().close());
        assertEquals(LocalDate.of(2026, 10, 20), result.getData().getFirst().date());
    }
    @Test void rejectsNonGoldTickers() {
        var repo = mock(GoldPriceStore.class);
        assertThrows(IllegalArgumentException.class, () -> new GoldHistoryController(repo).history("HPG"));
        verifyNoInteractions(repo);
    }
    @Test void emptyHistoryStaysEmpty() {
        var repo = mock(GoldPriceStore.class);
        when(repo.history("GOLD_RING_9999")).thenReturn(List.of());
        assertTrue(new GoldHistoryController(repo).history("GOLD_RING_9999").getData().isEmpty());
    }
}
