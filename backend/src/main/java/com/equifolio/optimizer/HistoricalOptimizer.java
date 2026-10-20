package com.equifolio.optimizer;

import com.equifolio.market.MarketPrice;
import com.equifolio.market.MarketPriceRepository;
import java.time.LocalDate;
import java.util.*;
import org.springframework.stereotype.Service;

/** Long-only mean/variance optimization on aligned observed returns. No fixed mu/covariance. */
@Service
public class HistoricalOptimizer {
  private final MarketPriceRepository prices;

  public HistoricalOptimizer(MarketPriceRepository prices) {
    this.prices = prices;
  }

  public Map<String, Object> optimize(List<String> tickers, double lambda) {
    if (tickers == null
        || tickers.size() < 2
        || tickers.size() > 8
        || new HashSet<>(tickers).size() != tickers.size())
      throw new IllegalArgumentException("Chọn 2–8 mã tài sản khác nhau");
    if (!Double.isFinite(lambda) || lambda < 1 || lambda > 10)
      throw new IllegalArgumentException("Lambda phải từ 1 đến 10");
    List<Map<LocalDate, Double>> series = new ArrayList<>();
    TreeSet<LocalDate> dates = null;
    for (String ticker : tickers) {
      Map<LocalDate, Double> map = new TreeMap<>();
      for (MarketPrice p : prices.findByAsset_TickerOrderByTradeDateAsc(ticker))
        if (p.getPrice().signum() > 0 && !p.getTradeDate().isAfter(LocalDate.now()))
          map.put(p.getTradeDate(), p.getPrice().doubleValue());
      if (dates == null) dates = new TreeSet<>(map.keySet());
      else dates.retainAll(map.keySet());
      series.add(map);
    }
    if (dates == null || dates.size() < 61)
      throw new IllegalStateException("Cần ít nhất 61 ngày giá chung cho các tài sản");
    if (dates.last().isBefore(LocalDate.now().minusDays(7)))
      throw new IllegalStateException("Giá đã cũ hơn 7 ngày; hãy đồng bộ thị trường");
    List<LocalDate> ds = new ArrayList<>(dates);
    if (ds.size() > 253) ds = ds.subList(ds.size() - 253, ds.size());
    int n = tickers.size(), t = ds.size() - 1;
    double[][] r = new double[t][n];
    double[] mu = new double[n];
    for (int i = 0; i < t; i++)
      for (int j = 0; j < n; j++) {
        r[i][j] = series.get(j).get(ds.get(i + 1)) / series.get(j).get(ds.get(i)) - 1;
        mu[j] += r[i][j] / t;
      }
    double[][] cov = new double[n][n];
    for (int j = 0; j < n; j++)
      for (int k = 0; k < n; k++) {
        for (int i = 0; i < t; i++)
          cov[j][k] += (r[i][j] - mu[j]) * (r[i][k] - mu[k]) * 252 / (t - 1);
        // Small diagonal ridge keeps optimization stable for collinear series.
        if (j == k) cov[j][k] += 1e-8;
      }
    for (int j = 0; j < n; j++) mu[j] *= 252;
    double[] w = solve(mu, cov, lambda);
    List<Map<String, Object>> frontier = new ArrayList<>();
    for (double l = 1; l <= 10; l += .5) frontier.add(point(tickers, solve(mu, cov, l), mu, cov));
    return Map.of(
        "tickers",
        tickers,
        "observations",
        t,
        "from",
        ds.get(0),
        "to",
        ds.get(ds.size() - 1),
        "lambda",
        lambda,
        "optimal",
        point(tickers, w, mu, cov),
        "frontier",
        frontier,
        "annualMeanReturns",
        mu,
        "annualCovariance",
        cov,
        "method",
        "Projected gradient; long-only, fully invested; historical sample estimates");
  }

  static double[] solve(double[] mu, double[][] cov, double lambda) {
    int n = mu.length;
    double[] w = new double[n];
    Arrays.fill(w, 1.0 / n);
    double bound = 0;
    for (double[] row : cov) {
      double s = 0;
      for (double x : row) s += Math.abs(x);
      bound = Math.max(bound, s);
    }
    double step = 1 / Math.max(1, lambda * bound);
    for (int it = 0; it < 10000; it++) {
      double[] z = new double[n];
      for (int j = 0; j < n; j++) {
        double grad = -mu[j];
        for (int k = 0; k < n; k++) grad += lambda * cov[j][k] * w[k];
        z[j] = w[j] - step * grad;
      }
      double[] next = project(z);
      double diff = 0;
      for (int j = 0; j < n; j++) diff += Math.abs(next[j] - w[j]);
      w = next;
      if (diff < 1e-10) break;
    }
    return w;
  }

  static double[] project(double[] z) {
    double[] sorted = z.clone();
    Arrays.sort(sorted);
    double sum = 0, theta = 0;
    for (int j = 0; j < z.length; j++) {
      double u = sorted[z.length - 1 - j];
      sum += u;
      double th = (sum - 1) / (j + 1);
      if (u > th) theta = th;
    }
    double[] w = new double[z.length];
    for (int j = 0; j < w.length; j++) w[j] = Math.max(0, z[j] - theta);
    return w;
  }

  private Map<String, Object> point(List<String> tickers, double[] w, double[] mu, double[][] cov) {
    Map<String, Double> weights = new LinkedHashMap<>();
    double ret = 0, var = 0;
    for (int j = 0; j < w.length; j++) {
      weights.put(tickers.get(j), w[j]);
      ret += w[j] * mu[j];
      for (int k = 0; k < w.length; k++) var += w[j] * cov[j][k] * w[k];
    }
    return Map.of(
        "weights", weights, "annualReturn", ret, "annualVolatility", Math.sqrt(Math.max(0, var)));
  }
}
