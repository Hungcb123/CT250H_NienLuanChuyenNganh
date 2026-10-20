package com.equifolio.optimizer;

import com.equifolio.ledger.PortfolioValuationDTO;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Compares server-generated plans; clients cannot submit or replace the actual actions. */
public final class RebalancePlanFingerprint {
    private RebalancePlanFingerprint() {}
    public static String of(Long userId, PortfolioValuationDTO valuation, RebalancePlanDTO plan) {
        var data = new ArrayList<String>();
        data.add(String.valueOf(userId));
        data.add(String.valueOf(plan.isTaaEnabled()));
        data.add(String.valueOf(plan.getHorizonSessions()));
        data.add(plan.getEquityPreference()==null?"UNSET":plan.getEquityPreference().mode());
        data.add(plan.getEquityPreference()==null?"UNSET":number(plan.getEquityPreference().etfWeight()));
        data.add(number(valuation.getTotalNetWorth()));
        data.add(number(valuation.getCashBalance()));
        new TreeMap<>(plan.getTargetAllocations()).forEach((key, value) -> {data.add(key); data.add(number(value));});
        valuation.getHoldings().stream().sorted(Comparator.comparing(PortfolioValuationDTO.HoldingItem::getAccountCode))
                .forEach(h -> { data.add(h.getAccountCode()); data.add(h.getTicker()); data.add(number(h.getQuantity())); data.add(number(h.getCurrentPrice())); });
        for (var a : plan.getActions()) {
            data.add(a.getActionType()); data.add(a.getTicker()); data.add(String.valueOf(a.isEarlySettlement())); data.add(number(a.getRoundedQuantity()));
            data.add(number(a.getEstimatedPrice())); data.add(number(a.getEstimatedTotalMoney()));
            data.add(number(a.getEstimatedFee())); data.add(number(a.getEstimatedTax())); data.add(number(a.getNetMoney()));
        }
        try {
            // Length framing prevents ambiguity between adjacent fields.
            StringBuilder framed = new StringBuilder();
            for (String value : data) framed.append(value.length()).append(':').append(value);
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(framed.toString().getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); }
    }
    private static String number(BigDecimal value) { return value == null ? "null" : value.stripTrailingZeros().toPlainString(); }
}
