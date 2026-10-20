package com.equifolio.ledger;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class PreparedPerformanceMathTest {
    PortfolioSnapshot snap(int day,int nav) {
        var s=new PortfolioSnapshot();s.setSnapshotDate(LocalDate.of(2026,1,day));s.setTotalNav(BigDecimal.valueOf(nav));s.setVnindexValue(BigDecimal.valueOf(100));return s;
    }
    @Test void depositsAndWithdrawalsAreNotReturns() {
        var flows=new TreeMap<LocalDate,BigDecimal>();
        flows.put(LocalDate.of(2026,1,2),BigDecimal.valueOf(100));
        flows.put(LocalDate.of(2026,1,3),BigDecimal.valueOf(-50));
        var growth=PreparedPerformanceMath.growth(List.of(snap(1,100),snap(2,200),snap(3,150),snap(4,165)),flows);
        assertEquals(0,growth.get(LocalDate.of(2026,1,4)).index().compareTo(new BigDecimal("1.1")));
    }
    @Test void normalizationAtDifferentStartDatesNeedsOnlyDivision() {
        var points=PreparedPerformanceMath.growth(List.of(snap(1,100),snap(2,110),snap(3,121)),new TreeMap<>());
        var all=points.get(LocalDate.of(2026,1,3)).index();
        var fromSecond=all.divide(points.get(LocalDate.of(2026,1,2)).index());
        assertEquals(0,all.compareTo(new BigDecimal("1.21")));
        assertEquals(0,fromSecond.compareTo(new BigDecimal("1.1")));
    }
    @Test void leadingEmptyAccountAndFundingDoesNotInventReturn() {
        var flows=new TreeMap<LocalDate,BigDecimal>();flows.put(LocalDate.of(2026,1,2),BigDecimal.valueOf(100));
        var growth=PreparedPerformanceMath.growth(List.of(snap(1,0),snap(2,100),snap(3,110)),flows);
        assertEquals(0,growth.get(LocalDate.of(2026,1,3)).index().compareTo(new BigDecimal("1.1")));
    }
    @Test void irregularIntervalsUseWeightedCashFlows() {
        var flows=new TreeMap<LocalDate,BigDecimal>();flows.put(LocalDate.of(2026,1,2),BigDecimal.valueOf(100));
        var growth=PreparedPerformanceMath.growth(List.of(snap(1,100),snap(3,215)),flows);
        assertEquals(0,growth.get(LocalDate.of(2026,1,3)).index().compareTo(new BigDecimal("1.1")));
    }
}
