package com.equifolio.optimizer;

import com.equifolio.ledger.PortfolioValuationDTO.HoldingItem;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;
import java.util.function.Function;

/** Instrument selection is independent from the SAA/TAA asset-class allocation. */
public final class EquityInstrumentPlanner {
    private EquityInstrumentPlanner() {}
    public static boolean isEtf(String ticker){return "E1VFVN30".equals(ticker)||ticker.startsWith("FU");}
    public static Map<String,BigDecimal> targets(BigDecimal stockBudget, EquityPreferenceService.Preference preference,List<HoldingItem> holdings){
        Map<String,BigDecimal> targets=new LinkedHashMap<>();
        var stocks=holdings.stream().filter(h->"STOCK".equals(h.getAssetClass())).toList();
        stocks.forEach(h->targets.put(h.getTicker(),BigDecimal.ZERO));
        BigDecimal etfBudget=stockBudget.multiply(preference.etfWeight());
        if(etfBudget.signum()>0)targets.put("E1VFVN30",etfBudget);
        var individuals=stocks.stream().filter(h->!isEtf(h.getTicker()) && h.getMarketValue().signum()>0).toList();
        BigDecimal existing=individuals.stream().map(HoldingItem::getMarketValue).reduce(BigDecimal.ZERO,BigDecimal::add);
        if(existing.signum()>0){
            BigDecimal budget=stockBudget.subtract(etfBudget),remaining=budget;
            for(int i=0;i<individuals.size();i++){
                var h=individuals.get(i);
                BigDecimal value=i==individuals.size()-1?remaining:budget.multiply(h.getMarketValue()).divide(existing,4,RoundingMode.HALF_EVEN);
                targets.merge(h.getTicker(),value,BigDecimal::add);remaining=remaining.subtract(value);
            }
        }
        return targets;
    }
    public static BigDecimal drift(Map<String,BigDecimal> targets,List<HoldingItem> holdings,BigDecimal nav){
        BigDecimal max=BigDecimal.ZERO;
        for(var target:targets.entrySet()){
            BigDecimal current=value(holdings,target.getKey());
            max=max.max(current.subtract(target.getValue()).abs().divide(nav,8,RoundingMode.HALF_EVEN));
        }
        return max;
    }
    private static BigDecimal value(List<HoldingItem> holdings,String ticker){
        return holdings.stream().filter(h->ticker.equals(h.getTicker())&&"STOCK".equals(h.getAssetClass()))
            .map(HoldingItem::getMarketValue).reduce(BigDecimal.ZERO,BigDecimal::add);
    }
    public static List<RebalancePlanDTO.RebalanceAction> sells(Map<String,BigDecimal> targets,List<HoldingItem> holdings){
        var actions=new ArrayList<RebalancePlanDTO.RebalanceAction>();
        for(var h:holdings){
            if(!"STOCK".equals(h.getAssetClass())||h.getCurrentPrice().signum()<=0)continue;
            BigDecimal target=targets.getOrDefault(h.getTicker(),BigDecimal.ZERO);
            BigDecimal current=value(holdings,h.getTicker());
            BigDecimal excess=current.subtract(target);
            if(excess.signum()<=0)continue;
            BigDecimal quantity=excess.max(BigDecimal.ZERO).multiply(h.getMarketValue()).divide(current.max(BigDecimal.ONE),8,RoundingMode.DOWN)
                .divide(h.getCurrentPrice(),0,RoundingMode.DOWN).min(h.getQuantity())
                .divide(new BigDecimal("100"),0,RoundingMode.DOWN).multiply(new BigDecimal("100"));
            if(quantity.signum()>0)actions.add(action("SELL",h.getTicker(),h.getAssetName(),quantity,h.getCurrentPrice()));
        }
        return actions;
    }
    public record Purchases(List<RebalancePlanDTO.RebalanceAction> actions,BigDecimal remainingCash){}
    public static Purchases buys(Map<String,BigDecimal> targets,List<HoldingItem> holdings,BigDecimal cash,Function<String,BigDecimal> prices){
        var actions=new ArrayList<RebalancePlanDTO.RebalanceAction>();
        for(var target:targets.entrySet()){
            BigDecimal deficit=target.getValue().subtract(value(holdings,target.getKey()));
            if(deficit.signum()<=0)continue;
            BigDecimal price=prices.apply(target.getKey());
            if(price==null||price.signum()<=0)continue;
            BigDecimal quantity=RebalanceBudget.quantity(deficit.min(cash),price,100);
            if(quantity.signum()<=0)continue;
            var action=action("BUY",target.getKey(),"E1VFVN30".equals(target.getKey())?"ETF DCVFMVN30":target.getKey(),quantity,price);
            cash=cash.subtract(action.getNetMoney());actions.add(action);
        }
        return new Purchases(actions,cash);
    }
    private static RebalancePlanDTO.RebalanceAction action(String side,String ticker,String name,BigDecimal quantity,BigDecimal price){
        BigDecimal gross=quantity.multiply(price).setScale(4,RoundingMode.HALF_EVEN);
        BigDecimal fee=gross.multiply(new BigDecimal(".001")).setScale(0,RoundingMode.HALF_EVEN);
        BigDecimal tax="SELL".equals(side)?fee:BigDecimal.ZERO;
        var action=new RebalancePlanDTO.RebalanceAction(side,ticker,name,"STOCK",quantity,quantity,price,gross,
            "Điều chỉnh theo lựa chọn ETF/cổ phiếu; lô 100, trong ngân sách sau phí. Chỉ thực hiện khi xác nhận kế hoạch.");
        action.setEstimatedFee(fee);action.setEstimatedTax(tax);
        action.setNetMoney("SELL".equals(side)?gross.subtract(fee).subtract(tax):gross.add(fee));
        return action;
    }
}
