package com.equifolio.ledger;

import static org.junit.jupiter.api.Assertions.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.junit.jupiter.api.Test;

class PerformanceServiceTest {
  private PortfolioSnapshot snap(int day, double nav) {
    var s = new PortfolioSnapshot();
    s.setSnapshotDate(LocalDate.of(2025, 1, day));
    s.setTotalNav(BigDecimal.valueOf(nav));
    s.setVnindexValue(BigDecimal.valueOf(100));
    return s;
  }

  @Test
  void capitalInjectionIsNotProfit() {
    var result =
        PerformanceService.calculate(
            List.of(snap(1, 100), snap(2, 200), snap(3, 220)),
            Map.of(LocalDate.of(2025, 1, 2), 100.),
            0);
    assertEquals(.1, ((Number) result.get("totalReturn")).doubleValue(), 1e-10);
    assertEquals(0, ((Number) result.get("maxDrawdown")).doubleValue());
  }

  @Test
  void withdrawalIsNotDrawdown() {
    var result =
        PerformanceService.calculate(
            List.of(snap(1, 100), snap(2, 50), snap(3, 50)),
            Map.of(LocalDate.of(2025, 1, 2), -50.),
            0);
    assertEquals(0, ((Number) result.get("totalReturn")).doubleValue(), 1e-10);
    assertEquals(0, ((Number) result.get("maxDrawdown")).doubleValue());
  }

  @Test
  void xirrUsesActualDates() {
    LocalDate first = LocalDate.of(2024, 1, 1);
    Double rate = PerformanceService.xirr(Map.of(first, -100., first.plusDays(365), 110.));
    assertNotNull(rate);
    assertEquals(Math.pow(1.1, 365.25 / 365) - 1, rate, 1e-8);
  }
}
