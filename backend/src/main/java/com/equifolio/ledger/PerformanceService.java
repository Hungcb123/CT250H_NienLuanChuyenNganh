package com.equifolio.ledger;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class PerformanceService {
  private final PortfolioSnapshotRepository snapshots;
  private final JdbcTemplate jdbc;

  public PerformanceService(PortfolioSnapshotRepository snapshots, JdbcTemplate jdbc) {
    this.snapshots = snapshots;
    this.jdbc = jdbc;
  }

  public Map<String, Object> report(Long userId, double rf) {
    var snaps =
        snapshots.findByUserIdOrderBySnapshotDateAsc(userId).stream()
            .filter(s -> com.equifolio.common.DemoData.isAnalysisSource(s.getSnapshotSource()))
            .toList();
    if (snaps.size() < 3)
      return Map.of(
          "available",
          false,
          "reason",
          "Cần ít nhất 3 snapshot thực tế; không tự tạo lịch sử để tính hiệu suất");
    var result = new LinkedHashMap<>(calculate(snaps, loadFlows(userId), rf));
    result.put("dataKind", snaps.stream().anyMatch(s -> "DEMO".equals(s.getSnapshotSource())) ? "DEMO" : "OBSERVED");
    return result;
  }

  private Map<LocalDate, Double> loadFlows(Long userId) {
    Map<LocalDate, Double> flows = new TreeMap<>();
    jdbc.query(
        """
SELECT (t.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS day, SUM(-e.amount) AS flow
FROM entries e JOIN transactions t ON t.id=e.transaction_id JOIN accounts a ON a.id=e.account_id
WHERE t.user_id=? AND t.status='POSTED' AND a.account_code='EQUITY_CAPITAL' AND t.type IN ('CAPITAL_INJECTION', 'CAPITAL_WITHDRAWAL')
GROUP BY day ORDER BY day
""",
        rs -> {
          flows.put(rs.getDate("day").toLocalDate(), rs.getDouble("flow"));
        },
        userId);
    return flows;
  }

  public Map<LocalDate, BigDecimal> historyGrowth(Long userId, List<PortfolioSnapshot> snaps) {
    Map<LocalDate, BigDecimal> growth = new HashMap<>();
    if (snaps.size() < 2) return growth;
    var result = calculate(snaps, loadFlows(userId), 0);
    if (!Boolean.TRUE.equals(result.get("available"))) return growth;
    @SuppressWarnings("unchecked")
    var curve = (List<Map<String, Object>>) result.get("curve");
    for (var point : curve)
      growth.put(
          (LocalDate) point.get("date"),
          BigDecimal.valueOf((((Number) point.get("growthIndex")).doubleValue() - 1) * 100)
              .setScale(2, RoundingMode.HALF_EVEN));
    return growth;
  }

  static Map<String, Object> calculate(
      List<PortfolioSnapshot> snaps, Map<LocalDate, Double> flows, double rf) {
    List<Double> returns = new ArrayList<>(), benchmark = new ArrayList<>();
    double index = 1, peak = 1, drawdown = 0;
    List<Map<String, Object>> curve = new ArrayList<>();
    for (int i = 1; i < snaps.size(); i++) {
      var a = snaps.get(i - 1);
      var b = snaps.get(i);
      long days = ChronoUnit.DAYS.between(a.getSnapshotDate(), b.getSnapshotDate());
      if (days <= 0) throw new IllegalStateException("Snapshot không theo thứ tự ngày");
      double flow = 0, weighted = 0;
      for (var f : flows.entrySet())
        if (f.getKey().isAfter(a.getSnapshotDate()) && !f.getKey().isAfter(b.getSnapshotDate())) {
          flow += f.getValue();
          weighted +=
              f.getValue() * ChronoUnit.DAYS.between(f.getKey(), b.getSnapshotDate()) / days;
        }
      double base = a.getTotalNav().doubleValue() + weighted;
      if (base <= 0)
        return Map.of(
            "available", false, "reason", "NAV đầu kỳ không dương; chưa thể tính lợi suất");
      double r = (b.getTotalNav().doubleValue() - a.getTotalNav().doubleValue() - flow) / base;
      if (!Double.isFinite(r) || r <= -1)
        return Map.of("available", false, "reason", "Lợi suất kỳ không hợp lệ");
      index *= 1 + r;
      peak = Math.max(peak, index);
      drawdown = Math.max(drawdown, 1 - index / peak);
      // Normalize irregular snapshot intervals to a calendar-day rate.
      returns.add(Math.expm1(Math.log1p(r) / days));
      double prev = a.getVnindexValue().doubleValue(), cur = b.getVnindexValue().doubleValue();
      benchmark.add(prev > 0 && cur > 0 ? Math.expm1(Math.log(cur / prev) / days) : Double.NaN);
      curve.add(Map.of("date", b.getSnapshotDate(), "growthIndex", index, "externalFlow", flow));
    }
    double mean = returns.stream().mapToDouble(x -> x).average().orElse(0), var = 0;
    for (double r : returns) var += (r - mean) * (r - mean);
    double vol = returns.size() > 1 ? Math.sqrt(var / (returns.size() - 1)) * Math.sqrt(365.25) : 0;
    long elapsed =
        ChronoUnit.DAYS.between(
            snaps.get(0).getSnapshotDate(), snaps.get(snaps.size() - 1).getSnapshotDate());
    double annual = Math.expm1(Math.log(index) * 365.25 / elapsed),
        sharpe = vol > 0 ? (mean * 365.25 - rf / 100) / vol : 0;
    double benchmarkGrowth = 1;
    for (int i = 1; i < snaps.size(); i++) {
      double a = snaps.get(i - 1).getVnindexValue().doubleValue(),
          b = snaps.get(i).getVnindexValue().doubleValue();
      if (a <= 0 || b <= 0) {
        benchmarkGrowth = Double.NaN;
        break;
      }
      benchmarkGrowth *= b / a;
    }
    Map<String, Object> out = new LinkedHashMap<>();
    out.put("available", true);
    out.put("totalReturn", index - 1);
    out.put("annualReturn", annual);
    out.put("annualVolatility", vol);
    out.put("sharpe", sharpe);
    out.put("maxDrawdown", drawdown);
    out.put("curve", curve);
    out.put("excessReturn", Double.isFinite(benchmarkGrowth) ? index - benchmarkGrowth : null);
    out.put(
        "method",
        "Linked Modified Dietz, end-of-day external flows; daily-rate normalization, 365.25"
            + " annualization. Not exact intraday TWR. Sparse snapshots smooth volatility.");
    Map<LocalDate, Double> investorFlows = new TreeMap<>();
    investorFlows.put(snaps.get(0).getSnapshotDate(), -snaps.get(0).getTotalNav().doubleValue());
    for (var f : flows.entrySet())
      if (f.getKey().isAfter(snaps.get(0).getSnapshotDate())
          && !f.getKey().isAfter(snaps.get(snaps.size() - 1).getSnapshotDate()))
        investorFlows.merge(f.getKey(), -f.getValue(), Double::sum);
    investorFlows.merge(
        snaps.get(snaps.size() - 1).getSnapshotDate(),
        snaps.get(snaps.size() - 1).getTotalNav().doubleValue(),
        Double::sum);
    out.put("xirr", xirr(investorFlows));
    return out;
  }

  static Double xirr(Map<LocalDate, Double> flows) {
    if (flows.size() < 2) return null;
    LocalDate first = Collections.min(flows.keySet());
    java.util.function.DoubleUnaryOperator npv =
        r -> {
          double sum = 0;
          for (var f : flows.entrySet())
            sum +=
                f.getValue() / Math.pow(1 + r, ChronoUnit.DAYS.between(first, f.getKey()) / 365.25);
          return sum;
        };
    double lo = -.9999, hi = 1;
    while (npv.applyAsDouble(lo) * npv.applyAsDouble(hi) > 0 && hi < 1024) hi = hi * 2 + 1;
    if (npv.applyAsDouble(lo) * npv.applyAsDouble(hi) > 0) return null;
    for (int i = 0; i < 200; i++) {
      double mid = (lo + hi) / 2;
      if (npv.applyAsDouble(lo) * npv.applyAsDouble(mid) <= 0) hi = mid;
      else lo = mid;
    }
    return (lo + hi) / 2;
  }

  public RiskMetricsDTO metrics(Long userId, double rf) {
    var r = report(userId, rf);
    RiskMetricsDTO dto = new RiskMetricsDTO();
    dto.setRiskFreeRatePercent(BigDecimal.valueOf(rf));
    if (!Boolean.TRUE.equals(r.get("available"))) {
      dto.setInterpretation(r.get("reason").toString());
      dto.setRiskRating("INSUFFICIENT_DATA");
      return dto;
    }
    dto.setSharpeRatio(number(r, "sharpe", 1));
    dto.setMaxDrawdownPercent(number(r, "maxDrawdown", 100));
    dto.setAnnualizedReturnPercent(number(r, "annualReturn", 100));
    dto.setAnnualizedVolatilityPercent(number(r, "annualVolatility", 100));
    dto.setAlphaPercent(r.get("excessReturn") == null ? null : number(r, "excessReturn", 100));
    dto.setBeta(null);
    dto.setRiskRating("HISTORICAL");
    dto.setInterpretation(
        ("DEMO".equals(r.get("dataKind")) ? "Dữ liệu mô phỏng kiểm thử. " : "") + "Hiệu suất lịch sử đã điều chỉnh vốn nạp/rút bằng Modified Dietz; Alpha hiển thị là chênh"
            + " lệch lợi suất so với VNINDEX, không phải Jensen alpha.");
    return dto;
  }

  private BigDecimal number(Map<String, Object> r, String key, double scale) {
    return BigDecimal.valueOf(((Number) r.get(key)).doubleValue() * scale)
        .setScale(4, RoundingMode.HALF_EVEN);
  }
}
