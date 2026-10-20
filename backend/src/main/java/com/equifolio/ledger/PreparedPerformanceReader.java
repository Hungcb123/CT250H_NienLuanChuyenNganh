package com.equifolio.ledger;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.*;
import java.math.*;
import java.time.*;
import java.util.*;

@Service
public class PreparedPerformanceReader {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    public PreparedPerformanceReader(JdbcTemplate jdbc,ObjectMapper mapper) {this.jdbc=jdbc;this.mapper=mapper;}
    record Head(long generation,long version,String generated,String priceDate,boolean provisional,boolean updating,int formula) {}
    record Point(LocalDate date,BigDecimal nav,BigDecimal stock,BigDecimal gold,BigDecimal savings,BigDecimal cash,BigDecimal growth,BigDecimal benchmark) {}

    @Transactional(readOnly=true,isolation=Isolation.REPEATABLE_READ)
    public PortfolioHistoryDTO history(Long userId,String timeframe) {
        String tf=timeframe==null?"1M":timeframe.trim().toUpperCase();
        if(!Set.of("1W","1M","3M","6M","YTD","1Y","ALL").contains(tf))tf="1M";
        var dto=new PortfolioHistoryDTO();dto.setTimeframe(tf);dto.setAlphaPercent(null);
        var heads=jdbc.query("""
            SELECT h.*,EXISTS(SELECT 1 FROM performance_dirty d WHERE d.user_id=h.user_id) AS updating
            FROM performance_head h WHERE h.user_id=?
            """,(rs,n)->new Head(rs.getLong("generation"),rs.getLong("input_version"),rs.getTimestamp("generated_at").toInstant().toString(),
                rs.getString("price_as_of"),rs.getBoolean("provisional"),rs.getBoolean("updating"),rs.getInt("formula_version")),userId);
        if(heads.isEmpty()) {dto.setStatus("PREPARING");dto.setUpdating(true);return dto;}
        var head=heads.getFirst();
        dto.setDataVersion(Long.toString(head.generation()));dto.setFormulaVersion(head.formula());
        dto.setGeneratedAt(head.generated());dto.setPriceAsOf(head.priceDate());dto.setProvisional(head.provisional());
        dto.setUpdating(head.updating());dto.setStatus(head.updating()?"UPDATING":"READY");
        LocalDate today=LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh"));
        LocalDate cutoff=switch(tf) {
            case "1W"->today.minusDays(7);case "1M"->today.minusMonths(1);case "3M"->today.minusMonths(3);
            case "6M"->today.minusMonths(6);case "1Y"->today.minusYears(1);case "YTD"->LocalDate.of(today.getYear(),1,1);
            default->LocalDate.of(1,1,1);
        };
        var rows=jdbc.query("""
            SELECT p.*,COALESCE(b.close,0) AS benchmark FROM performance_daily p
            JOIN performance_head h ON h.user_id=p.user_id AND h.generation=p.generation
            LEFT JOIN LATERAL(SELECT close FROM benchmark_daily WHERE generation=h.benchmark_generation
                AND price_date<=p.snapshot_date ORDER BY price_date DESC LIMIT 1) b ON TRUE
            WHERE p.user_id=? AND p.generation=? AND p.snapshot_date>=? ORDER BY p.snapshot_date
            """,(rs,n)->new Point(rs.getDate("snapshot_date").toLocalDate(),rs.getBigDecimal("nav"),rs.getBigDecimal("stock"),
                rs.getBigDecimal("gold"),rs.getBigDecimal("savings"),rs.getBigDecimal("cash"),rs.getBigDecimal("growth_index"),rs.getBigDecimal("benchmark")),
                userId,head.generation(),cutoff);
        if(rows.isEmpty())return dto;
        BigDecimal base=rows.getFirst().growth(),benchmark=rows.getFirst().benchmark();
        List<PortfolioHistoryDTO.SnapshotPoint> points=new ArrayList<>();
        for(var p:rows)points.add(new PortfolioHistoryDTO.SnapshotPoint(p.date().toString(),p.nav(),p.stock(),p.gold(),p.savings(),p.cash(),
            percent(p.growth(),base),percent(p.benchmark(),benchmark),p.benchmark()));
        var last=points.getLast();dto.setPoints(points);dto.setCurrentNav(last.getNav());
        dto.setPortfolioReturnPercent(last.getNavReturn());dto.setVniReturnPercent(last.getVniReturn());
        if(benchmark.signum()>0&&points.stream().allMatch(p->p.getVnindex().signum()>0))
            dto.setAlphaPercent(last.getNavReturn().subtract(last.getVniReturn()));
        return dto;
    }
    private BigDecimal percent(BigDecimal value,BigDecimal base) {
        if(value==null||base==null||base.signum()<=0||value.signum()<0)return BigDecimal.ZERO;
        return value.divide(base,16,RoundingMode.HALF_EVEN).subtract(BigDecimal.ONE).movePointRight(2).setScale(2,RoundingMode.HALF_EVEN);
    }
    @Transactional(readOnly=true)
    public RiskMetricsDTO risk(Long userId) {
        var rows=jdbc.query("SELECT risk_payload::text FROM performance_head WHERE user_id=?",(rs,n)->rs.getString(1),userId);
        if(rows.isEmpty()) {var result=new RiskMetricsDTO();result.setRiskRating("INSUFFICIENT_DATA");result.setInterpretation("Đang chuẩn bị dữ liệu hiệu suất.");return result;}
        try {return mapper.readValue(rows.getFirst(),RiskMetricsDTO.class);}
        catch(Exception e){throw new IllegalStateException("Invalid prepared performance data",e);}
    }
}
