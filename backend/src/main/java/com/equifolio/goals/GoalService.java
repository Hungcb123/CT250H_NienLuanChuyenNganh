package com.equifolio.goals;

import jakarta.validation.constraints.*;
import java.time.*;
import java.time.temporal.ChronoUnit;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class GoalService {
  private final JdbcTemplate jdbc;

  public GoalService(JdbcTemplate jdbc) {
    this.jdbc = jdbc;
  }

  public record GoalInput(
      @NotBlank @Size(max = 120) String title,
      @Positive @Max(100000000000000L) double targetAmount,
      @PositiveOrZero @Max(100000000000000L) double allocatedAmount,
      @PositiveOrZero @Max(100000000000000L) double monthlyContribution,
      @DecimalMin("-50") @DecimalMax("50") double annualRate,
      @NotNull @Future LocalDate targetDate,
      long version) {}

  public List<Map<String, Object>> list(Long user) {
    return jdbc.query(
        "SELECT * FROM financial_goals WHERE user_id=? ORDER BY target_date,id",
        (rs, i) -> {
          var row = new LinkedHashMap<String, Object>();
          row.put("id", rs.getLong("id"));
          row.put("title", rs.getString("title"));
          row.put("version", rs.getLong("version"));
          LocalDate date = rs.getDate("target_date").toLocalDate();
          row.put("targetDate", date);
          double target = rs.getDouble("target_amount"),
              allocated = rs.getDouble("allocated_amount"),
              monthly = rs.getDouble("monthly_contribution"),
              rate = rs.getDouble("annual_rate");
          row.put("targetAmount", target);
          row.put("allocatedAmount", allocated);
          row.put("monthlyContribution", monthly);
          row.put("annualRate", rate);
          row.putAll(project(target, allocated, monthly, rate, date));
          return row;
        },
        user);
  }

  public Long save(Long user, Long id, GoalInput g) {
    if (g.targetDate().isAfter(LocalDate.now().plusYears(50)))
      throw new IllegalArgumentException("Thời hạn tối đa 50 năm");
    if (!Double.isFinite(
        g.targetAmount() + g.allocatedAmount() + g.monthlyContribution() + g.annualRate()))
      throw new IllegalArgumentException("Số liệu không hợp lệ");
    if (id == null)
      return jdbc.queryForObject(
          """
INSERT INTO financial_goals(user_id,title,target_amount,allocated_amount,monthly_contribution,annual_rate,target_date)
VALUES(?,?,?,?,?,?,?) RETURNING id
""",
          Long.class,
          user,
          g.title().trim(),
          g.targetAmount(),
          g.allocatedAmount(),
          g.monthlyContribution(),
          g.annualRate(),
          g.targetDate());
    int changed =
        jdbc.update(
            """
UPDATE financial_goals SET title=?,target_amount=?,allocated_amount=?,monthly_contribution=?,annual_rate=?,target_date=?,version=version+1
WHERE id=? AND user_id=? AND version=?
""",
            g.title().trim(),
            g.targetAmount(),
            g.allocatedAmount(),
            g.monthlyContribution(),
            g.annualRate(),
            g.targetDate(),
            id,
            user,
            g.version());
    if (changed != 1)
      throw new IllegalStateException("Mục tiêu đã thay đổi hoặc không tồn tại; hãy tải lại");
    return id;
  }

  public void delete(Long user, Long id) {
    if (jdbc.update("DELETE FROM financial_goals WHERE id=? AND user_id=?", id, user) != 1)
      throw new IllegalArgumentException("Không tìm thấy mục tiêu");
  }

  static Map<String, Object> project(
      double target, double principal, double monthly, double annual, LocalDate date) {
    long months = Math.max(0, ChronoUnit.MONTHS.between(YearMonth.now(), YearMonth.from(date)));
    double r = Math.pow(1 + annual / 100, 1. / 12) - 1, factor = Math.pow(1 + r, months);
    double annuity = Math.abs(r) < 1e-12 ? months : (factor - 1) / r;
    double fv = principal * factor + monthly * annuity;
    double required =
        annuity > 0
            ? Math.max(0, (target - principal * factor) / annuity)
            : Math.max(0, target - principal);
    return Map.of(
        "monthsRemaining",
        months,
        "projectedAmount",
        fv,
        "requiredMonthlyContribution",
        required,
        "shortfall",
        Math.max(0, target - fv),
        "progressPercent",
        Math.min(100, principal / target * 100),
        "assumptions",
        "Góp cuối tháng; lãi suất giả định cố định; vốn phân bổ do bạn khai báo, không tự trích"
            + " NAV");
  }
}
