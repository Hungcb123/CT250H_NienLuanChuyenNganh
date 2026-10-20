package com.equifolio.ledger;

import java.math.*;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.*;

public final class PreparedPerformanceMath {
    private PreparedPerformanceMath() {}
    public record Growth(BigDecimal index,BigDecimal flow) {}
    public static Map<LocalDate,Growth> growth(List<PortfolioSnapshot> snaps,NavigableMap<LocalDate,BigDecimal> flows) {
        Map<LocalDate,Growth> result=new LinkedHashMap<>();
        if(snaps.isEmpty())return result;
        BigDecimal index=BigDecimal.ONE;
        result.put(snaps.getFirst().getSnapshotDate(),new Growth(index,BigDecimal.ZERO));
        for(int i=1;i<snaps.size();i++) {
            var a=snaps.get(i-1);var b=snaps.get(i);
            long days=ChronoUnit.DAYS.between(a.getSnapshotDate(),b.getSnapshotDate());
            if(days<=0)throw new IllegalArgumentException("Snapshots must be ordered");
            BigDecimal flow=BigDecimal.ZERO,weighted=BigDecimal.ZERO;
            for(var f:flows.subMap(a.getSnapshotDate(),false,b.getSnapshotDate(),true).entrySet()) {
                flow=flow.add(f.getValue());
                weighted=weighted.add(f.getValue().multiply(BigDecimal.valueOf(ChronoUnit.DAYS.between(f.getKey(),b.getSnapshotDate()))).divide(BigDecimal.valueOf(days),16,RoundingMode.HALF_EVEN));
            }
            var base=a.getTotalNav().add(weighted);
            var profit=b.getTotalNav().subtract(a.getTotalNav()).subtract(flow);
            if(base.signum()<=0) {
                if(profit.signum()!=0)throw new IllegalStateException("Cannot measure return without invested capital");
            } else {
                var factor=BigDecimal.ONE.add(profit.divide(base,16,RoundingMode.HALF_EVEN));
                if(factor.signum()<0)throw new IllegalStateException("Invalid negative growth factor");
                index=index.multiply(factor).setScale(16,RoundingMode.HALF_EVEN);
            }
            result.put(b.getSnapshotDate(),new Growth(index,flow));
        }
        return result;
    }
    public static RiskMetricsDTO risk(List<PortfolioSnapshot> snaps,NavigableMap<LocalDate,BigDecimal> flows,double rf,boolean demo) {
        var dto=new RiskMetricsDTO();dto.setRiskFreeRatePercent(BigDecimal.valueOf(rf));dto.setRiskRating("INSUFFICIENT_DATA");
        dto.setInterpretation("Chưa đủ lịch sử để tính hiệu suất.");
        int first=0;while(first<snaps.size()&&snaps.get(first).getTotalNav().signum()<=0)first++;
        snaps=snaps.subList(first,snaps.size());
        if(snaps.size()<3)return dto;
        Map<LocalDate,Double> doubles=new TreeMap<>();flows.forEach((day,value)->doubles.put(day,value.doubleValue()));
        var report=PerformanceService.calculate(snaps,doubles,rf);
        if(!Boolean.TRUE.equals(report.get("available")))return dto;
        dto.setAnnualizedReturnPercent(number(report,"annualReturn",100));
        dto.setAnnualizedVolatilityPercent(number(report,"annualVolatility",100));
        dto.setMaxDrawdownPercent(number(report,"maxDrawdown",100));dto.setSharpeRatio(number(report,"sharpe",1));
        dto.setAlphaPercent(number(report,"excessReturn",100));dto.setBeta(null);dto.setRiskRating("HISTORICAL");
        dto.setInterpretation((demo?"Dữ liệu mô phỏng kiểm thử. ":"")+"Lợi suất đã điều chỉnh tiền nạp/rút bằng Linked Modified Dietz; dữ liệu được chuẩn bị ở nền.");
        return dto;
    }
    private static BigDecimal number(Map<String,Object> map,String key,double scale) {
        Object value=map.get(key);
        if(!(value instanceof Number n)||!Double.isFinite(n.doubleValue()))return null;
        return BigDecimal.valueOf(n.doubleValue()*scale).setScale(4,RoundingMode.HALF_EVEN);
    }
}
