package com.equifolio.goals;

import static org.junit.jupiter.api.Assertions.*;

import java.time.*;
import org.junit.jupiter.api.Test;

class GoalServiceTest {
  @Test
  void zeroInterestRequiredContribution() {
    var result = GoalService.project(1200, 0, 100, 0, LocalDate.now().plusYears(1));
    assertEquals(1200, ((Number) result.get("projectedAmount")).doubleValue(), 1e-9);
    assertEquals(100, ((Number) result.get("requiredMonthlyContribution")).doubleValue(), 1e-9);
  }

  @Test
  void completedGoalNeverRequiresNegativeSavings() {
    var result = GoalService.project(1000, 2000, 0, 5, LocalDate.now().plusYears(1));
    assertEquals(0, ((Number) result.get("requiredMonthlyContribution")).doubleValue());
    assertEquals(0, ((Number) result.get("shortfall")).doubleValue());
  }
}
