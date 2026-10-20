package com.equifolio.ledger;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowCallbackHandler;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.sql.ResultSet;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class PerformanceWithdrawalTest {
    @Test void persistedWithdrawalIsIncludedAsNegativeFlow() {
        var jdbc = mock(JdbcTemplate.class);
        doAnswer(inv -> {
            String sql = inv.getArgument(0);
            assertTrue(sql.contains("'CAPITAL_WITHDRAWAL'"));
            ResultSet row = mock(ResultSet.class);
            when(row.getDate("day")).thenReturn(java.sql.Date.valueOf("2025-01-02"));
            when(row.getDouble("flow")).thenReturn(-50.);
            ((RowCallbackHandler) inv.getArgument(1)).processRow(row);
            return null;
        }).when(jdbc).query(anyString(), any(RowCallbackHandler.class), eq(7L));
        var service = new PerformanceService(mock(PortfolioSnapshotRepository.class), jdbc);
        var snaps = List.of(snapshot(1, 100), snapshot(2, 50), snapshot(3, 50));
        var growth = service.historyGrowth(7L, snaps);
        assertFalse(growth.isEmpty());
        assertTrue(growth.values().stream().allMatch(value -> value.signum() == 0));
        verify(jdbc).query(anyString(), any(RowCallbackHandler.class), eq(7L));
    }
    private PortfolioSnapshot snapshot(int day, int nav) {
        var s = new PortfolioSnapshot();
        s.setSnapshotDate(LocalDate.of(2025, 1, day));
        s.setTotalNav(BigDecimal.valueOf(nav));
        s.setVnindexValue(BigDecimal.valueOf(100));
        return s;
    }
}
