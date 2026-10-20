package com.equifolio.optimizer;
import java.math.BigDecimal;
import java.math.RoundingMode;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class RebalanceBudgetTest {
    @Test void roundedFeesNeverOverdrawBudgetAtWholeLotBoundaries() {
        for(String p:new String[]{"1.4999","99.9999","10000.0001","10000000"}) {
            BigDecimal price=new BigDecimal(p);
            for(int lot:new int[]{1,100}) for(int offset=-2;offset<=2;offset++) {
                BigDecimal budget=price.multiply(BigDecimal.valueOf(lot*3L)).multiply(new BigDecimal("1.001")).add(new BigDecimal(offset).movePointLeft(4));
                BigDecimal quantity=RebalanceBudget.quantity(budget,price,lot);
                assertEquals(0,quantity.remainder(BigDecimal.valueOf(lot)).signum());
                BigDecimal gross=quantity.multiply(price).setScale(4,RoundingMode.HALF_EVEN);
                BigDecimal cost=gross.add(gross.multiply(new BigDecimal("0.001")).setScale(0,RoundingMode.HALF_EVEN));
                assertTrue(cost.compareTo(budget)<=0,()->"budget="+budget+", cost="+cost);
            }
        }
    }
}
