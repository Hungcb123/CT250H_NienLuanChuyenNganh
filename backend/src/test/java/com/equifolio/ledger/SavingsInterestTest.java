package com.equifolio.ledger;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.LocalDate;
import static org.junit.jupiter.api.Assertions.*;
class SavingsInterestTest {
    @Test void earlyWithdrawalUsesDemandRateAndMaturityUsesContractRate() {
        var d=new SavingsDeposit();d.setPrincipalAmount(new BigDecimal("36500000"));d.setInterestRate(new BigDecimal("5.5"));
        d.setStartDate(LocalDate.of(2026,1,1));d.setMaturityDate(d.getStartDate().plusDays(180));
        assertEquals(new BigDecimal("1000"),SavingsInterest.accrued(d,d.getStartDate().plusDays(10),new BigDecimal("0.1")));
        assertEquals(new BigDecimal("990000"),SavingsInterest.accrued(d,d.getMaturityDate(),new BigDecimal("0.1")));
        assertEquals(new BigDecimal("990000"),SavingsInterest.accrued(d,d.getMaturityDate().plusDays(100),new BigDecimal("0.1")));
    }
    @Test void missingDatesCannotFabricateInterest() {
        assertThrows(IllegalStateException.class,()->SavingsInterest.accrued(new SavingsDeposit(),LocalDate.now(),new BigDecimal("0.1")));
    }
}
