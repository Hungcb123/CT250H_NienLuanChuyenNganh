package com.equifolio.common;

import com.equifolio.profile.User;
import com.equifolio.ledger.PerformanceService;
import com.equifolio.ledger.PortfolioSnapshot;
import com.equifolio.ledger.PortfolioSnapshotRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class DemoDataTest {
    @Test void simulationIsExplicitAndLegacyHistoryStaysExcluded() {
        assertTrue(DemoData.isAnalysisSource("DEMO"));
        assertTrue(DemoData.isAnalysisSource("OBSERVED"));
        assertFalse(DemoData.isAnalysisSource("LEGACY_UNVERIFIED"));
        assertFalse(DemoData.isAnalysisSource(null));
        User user = new User(); user.setUsername("demo_balanced");user.setEmail("someone@example.test");
        assertFalse(DemoData.isDemoAccount(user));
        user.setEmail("demo_balanced@demo.equifolio.test");assertTrue(DemoData.isDemoAccount(user));
    }
    @Test void reportLabelsDemoAndIgnoresLegacyOutlier() {
        var repository = mock(PortfolioSnapshotRepository.class);
        PortfolioSnapshot a=snapshot(4,100,"DEMO"), b=snapshot(3,101,"DEMO"), c=snapshot(2,102,"DEMO");
        var legacy=snapshot(5,1_000_000,"LEGACY_UNVERIFIED");
        when(repository.findByUserIdOrderBySnapshotDateAsc(10L)).thenReturn(List.of(legacy,a,b,c));
        var service=new PerformanceService(repository,mock(JdbcTemplate.class));
        var report=service.report(10L,4.5);
        assertEquals(true,report.get("available"));assertEquals("DEMO",report.get("dataKind"));
        assertEquals(.02,((Number)report.get("totalReturn")).doubleValue(),1e-10);
        assertTrue(service.metrics(10L,4.5).getInterpretation().contains("mô phỏng"));
    }
    private PortfolioSnapshot snapshot(int ago,double nav,String source){
        var result=new PortfolioSnapshot();result.setSnapshotDate(LocalDate.now().minusDays(ago));
        result.setTotalNav(BigDecimal.valueOf(nav));result.setVnindexValue(new BigDecimal("1000"));
        result.setSnapshotSource(source);return result;
    }
}
