package com.equifolio.optimizer;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** Affordable whole lots, using the same gross/fee rounding as the executor. */
public final class RebalanceBudget {
    private RebalanceBudget() {}
    public static BigDecimal quantity(BigDecimal budget, BigDecimal price, int lotSize) {
        if (budget.signum() <= 0 || price.signum() <= 0 || lotSize <= 0) return BigDecimal.ZERO;
        BigDecimal lot = BigDecimal.valueOf(lotSize);
        BigDecimal quantity = budget.divide(price.multiply(new BigDecimal("1.001")), 0, RoundingMode.FLOOR)
                .divide(lot, 0, RoundingMode.FLOOR).multiply(lot);
        while (quantity.signum() > 0) {
            BigDecimal gross = quantity.multiply(price).setScale(4, RoundingMode.HALF_EVEN);
            BigDecimal fee = gross.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
            if (gross.add(fee).compareTo(budget) <= 0) break;
            quantity = quantity.subtract(lot);
        }
        return quantity;
    }
}
