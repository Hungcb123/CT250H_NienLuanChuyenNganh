package com.equifolio.optimizer;

import com.equifolio.ledger.*;
import com.equifolio.market.*;
import com.equifolio.profile.*;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class TaaRebalanceRegressionTest {
    static BigDecimal b(String s) { return new BigDecimal(s); }
    @Test void saleNetFundsAffordableGoldAndReservesCash() {
        Fixture f = new Fixture();
        var p = f.optimizer.generateRebalancePlan(1L);
        var buy = p.getActions().stream().filter(a -> a.getActionType().equals("BUY")).findFirst().orElseThrow();
        assertEquals(b("9"), buy.getRoundedQuantity());
        assertEquals(0,b("9710000").compareTo(p.getNetCashImpact()));
        assertNotNull(p.getPlanToken());
        f.targets("0", ".9", "0", ".1");
        p = f.optimizer.generateRebalancePlan(1L);
        assertTrue(p.getNetCashImpact().compareTo(b("10000000")) >= 0);
    }
    @Test void savingsPayoutIsIncludedInCashSummary() {
        Fixture f = new Fixture(); f.savingsOnly();
        var p = f.optimizer.generateRebalancePlan(1L);
        BigDecimal incoming = p.getActions().stream().filter(a -> a.getActionType().equals("SETTLE_SAVINGS")).map(a -> a.getNetMoney()).reduce(BigDecimal.ZERO, BigDecimal::add);
        BigDecimal outgoing = p.getActions().stream().filter(a -> a.getActionType().equals("BUY")).map(a -> a.getNetMoney()).reduce(BigDecimal.ZERO, BigDecimal::add);
        assertEquals(0, incoming.subtract(outgoing).compareTo(p.getNetCashImpact()));
        assertTrue(p.getNetCashImpact().signum() >= 0);
    }
    @Test void changedPriceRejectsPreviouslyReviewedPlanBeforeAnyPosting() {
        Fixture f = new Fixture(); var p = f.optimizer.generateRebalancePlan(1L);
        when(f.market.getLatestPrice("GOLD_SJC")).thenReturn(b("11000000"));
        assertThrows(IllegalStateException.class, () -> f.optimizer.executeRebalancePlan(1L,p.getPlanToken()));
        verifyNoInteractions(f.transactions);
        verify(f.accounts, never()).save(any());
        assertThrows(IllegalStateException.class, () -> f.optimizer.executeRebalancePlan(1L));
    }
    @Test void changedCashOrUserInvalidatesPlanFingerprint() {
        Fixture f = new Fixture(); var p = f.optimizer.generateRebalancePlan(1L);
        assertNotEquals(p.getPlanToken(),RebalancePlanFingerprint.of(2L,f.valuation,p));
        f.valuation.setCashBalance(b("1"));
        assertNotEquals(p.getPlanToken(),RebalancePlanFingerprint.of(1L,f.valuation,p));
    }
    @Test void settlementFailurePropagatesInsteadOfReportingSuccess() {
        Fixture f = new Fixture(); f.savingsOnly(); var p=f.optimizer.generateRebalancePlan(1L);
        doThrow(new IllegalStateException("settlement failed")).when(f.ledger).settleSavingsDeposit(10L);
        IllegalStateException e=assertThrows(IllegalStateException.class,()->f.optimizer.executeRebalancePlan(1L,p.getPlanToken()));
        assertEquals("settlement failed",e.getMessage());
        verify(f.transactions,never()).save(any());
    }
    static class Fixture {
        final LedgerService ledger=mock(LedgerService.class);
        final PortfolioTargetRepository targetRepo=mock(PortfolioTargetRepository.class);
        final MarketService market=mock(MarketService.class);
        final AccountRepository accounts=mock(AccountRepository.class);
        final TransactionRepository transactions=mock(TransactionRepository.class);
        final UserRepository users=mock(UserRepository.class);
        final AssetRepository assets=mock(AssetRepository.class);
        final SavingsDepositRepository deposits=mock(SavingsDepositRepository.class);
        final PortfolioValuationDTO valuation=new PortfolioValuationDTO();
        final PortfolioOptimizerService optimizer;
        Fixture() {
            var models=mock(OnnxRegimeService.class);
            when(models.predictStockRegime()).thenReturn(new RegimePrediction(0,0,"UNAVAILABLE"));
            when(models.predictGoldRegime()).thenReturn(new RegimePrediction(0,0,"UNAVAILABLE"));
            optimizer=new PortfolioOptimizerService(ledger,targetRepo,market,accounts,transactions,users,assets,models,deposits);
            ReflectionTestUtils.setField(optimizer,"stockModel","onnx");
            targets("0","1","0","0");
            valuation.setTotalNetWorth(b("100000000")); valuation.setStockValue(b("100000000")); valuation.setCashBalance(BigDecimal.ZERO);
            valuation.setCurrentAllocations(Map.of("STOCK",BigDecimal.ONE,"GOLD",BigDecimal.ZERO,"SAVINGS",BigDecimal.ZERO,"CASH",BigDecimal.ZERO,"CASH_SAVINGS",BigDecimal.ZERO));
            valuation.setHoldings(List.of(new PortfolioValuationDTO.HoldingItem("ASSET_HPG","HPG","HPG","STOCK",b("1000"),b("100000"),b("100000000"),BigDecimal.ONE)));
            when(ledger.calculatePortfolioValuation(1L)).thenReturn(valuation);
            when(market.getLatestPrice("GOLD_SJC")).thenReturn(b("10000000"));
            var user=new User();user.setId(1L);when(users.findById(1L)).thenReturn(Optional.of(user));
            var vnd=new Asset("VND","VND","CASH");when(assets.findById("VND")).thenReturn(Optional.of(vnd));
            when(accounts.findByUserIdAndAccountCode(1L,"VND_WALLET")).thenReturn(Optional.of(new Account(user,"VND_WALLET",vnd,BigDecimal.ZERO)));
        }
        void targets(String stock,String gold,String savings,String cash) {
            when(targetRepo.findByUserId(1L)).thenReturn(List.of(new PortfolioTarget(null,"STOCK",b(stock)),new PortfolioTarget(null,"GOLD",b(gold)),new PortfolioTarget(null,"SAVINGS",b(savings)),new PortfolioTarget(null,"CASH",b(cash))));
        }
        void savingsOnly() {
            valuation.setStockValue(BigDecimal.ZERO); valuation.setSavingsValue(b("100000000")); valuation.setHoldings(List.of());
            valuation.setCurrentAllocations(Map.of("STOCK",BigDecimal.ZERO,"GOLD",BigDecimal.ZERO,"SAVINGS",BigDecimal.ONE,"CASH",BigDecimal.ZERO,"CASH_SAVINGS",BigDecimal.ONE));
            var dep=new SavingsDeposit();dep.setId(10L);dep.setPrincipalAmount(b("100000000"));dep.setMaturityDate(LocalDate.now());
            when(deposits.findByUserIdAndStatus(1L,"ACTIVE")).thenReturn(List.of(dep));
            when(ledger.estimateSavingsPayout(dep)).thenReturn(b("100000000"));
        }
    }
}
