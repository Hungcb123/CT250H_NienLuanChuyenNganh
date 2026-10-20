package com.equifolio.optimizer;
import com.equifolio.ledger.PortfolioValuationDTO.HoldingItem;
import java.math.BigDecimal;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import org.springframework.test.util.ReflectionTestUtils;

class EquityInstrumentPlannerTest {
    static BigDecimal b(String s){return new BigDecimal(s);}
    static HoldingItem holding(String ticker,String qty,String price){
        return new HoldingItem("ASSET_"+ticker,ticker,ticker,"STOCK",b(qty),b(price),b(qty).multiply(b(price)),BigDecimal.ZERO);
    }
    @Test void etfChoiceConvertsEvenWhenTotalStockAllocationAlreadyMatches(){
        var f=new TaaRebalanceRegressionTest.Fixture();
        f.targets("1","0","0","0");
        var preferences=mock(EquityPreferenceService.class);
        when(preferences.get(1L)).thenReturn(new EquityPreferenceService.Preference("ETF",BigDecimal.ONE));
        ReflectionTestUtils.setField(f.optimizer,"equityPreferences",preferences);
        when(f.market.getLatestPrice("E1VFVN30")).thenReturn(b("30000"));
        var plan=f.optimizer.generateRebalancePlan(1L);
        assertTrue(plan.isDriftDetected());
        assertTrue(plan.getActions().stream().anyMatch(a->a.getActionType().equals("SELL")&&a.getTicker().equals("HPG")));
        var buys=plan.getActions().stream().filter(a->a.getActionType().equals("BUY")).toList();
        assertFalse(buys.isEmpty());
        assertTrue(buys.stream().allMatch(a->a.getTicker().equals("E1VFVN30")));
        assertTrue(plan.getNetCashImpact().signum()>=0);
        String reviewed=plan.getPlanToken();
        when(preferences.get(1L)).thenReturn(new EquityPreferenceService.Preference("MIXED",b(".5")));
        assertThrows(IllegalStateException.class,()->f.optimizer.executeRebalancePlan(1L,reviewed));
        verifyNoInteractions(f.transactions);
    }
    @Test void mixedTargetsSplitStockBudgetAndSellsFundAffordableLots(){
        var holdings=List.of(holding("FPT","1000","100000"));
        var targets=EquityInstrumentPlanner.targets(b("100000000"),new EquityPreferenceService.Preference("MIXED",b(".6")),holdings);
        assertEquals(0,b("60000000").compareTo(targets.get("E1VFVN30")));
        assertEquals(0,b("40000000").compareTo(targets.get("FPT")));
        var sells=EquityInstrumentPlanner.sells(targets,holdings);
        assertEquals(b("600"),sells.getFirst().getRoundedQuantity());
        var cash=sells.getFirst().getNetMoney();
        var buys=EquityInstrumentPlanner.buys(targets,holdings,cash,ticker->b("30000"));
        assertTrue(buys.remainingCash().signum()>=0);
        assertTrue(buys.actions().stream().allMatch(a->a.getTicker().equals("E1VFVN30")));
        assertEquals(BigDecimal.ZERO,buys.actions().getFirst().getRoundedQuantity().remainder(b("100")));
    }
    @Test void mixedSellsSmallIndividualPositionsToFundTheWholeEtfShare(){
        var holdings=new ArrayList<HoldingItem>();
        for(int i=0;i<12;i++)holdings.add(holding("STOCK"+i,"1000","25000"));
        var targets=EquityInstrumentPlanner.targets(b("300000000"),new EquityPreferenceService.Preference("MIXED",b(".6")),holdings);
        var sells=EquityInstrumentPlanner.sells(targets,holdings);
        assertEquals(12,sells.size());
        BigDecimal gross=sells.stream().map(RebalancePlanDTO.RebalanceAction::getEstimatedTotalMoney).reduce(BigDecimal.ZERO,BigDecimal::add);
        assertEquals(0,b("180000000").compareTo(gross));
    }
    @Test void stocksChoiceExcludesEtfAndNoPriceNeverCreatesBuy(){
        var holdings=List.of(holding("E1VFVN30","1000","30000"),holding("HPG","1000","25000"));
        var targets=EquityInstrumentPlanner.targets(b("100000000"),new EquityPreferenceService.Preference("STOCKS",BigDecimal.ZERO),holdings);
        assertEquals(BigDecimal.ZERO,targets.get("E1VFVN30"));
        assertEquals(0,b("100000000").compareTo(targets.get("HPG")));
        assertTrue(EquityInstrumentPlanner.buys(targets,holdings,b("100000000"),ticker->BigDecimal.ZERO).actions().isEmpty());
        assertTrue(EquityInstrumentPlanner.targets(b("100000000"),new EquityPreferenceService.Preference("STOCKS",BigDecimal.ZERO),List.of()).isEmpty());
    }
}
