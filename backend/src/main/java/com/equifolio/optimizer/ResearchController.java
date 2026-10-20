package com.equifolio.optimizer;

import com.equifolio.auth.SecurityUtils;
import com.equifolio.common.ApiResponse;
import com.equifolio.ledger.PerformanceService;
import com.equifolio.market.ExternalMarketSyncService;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import org.springframework.core.io.ClassPathResource;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/research")
public class ResearchController {
  private final HistoricalOptimizer optimizer;
  private final OnnxRegimeService models;
  private final PerformanceService performance;
  private final ExternalMarketSyncService market;
  private final ObjectMapper json;
  @org.springframework.beans.factory.annotation.Autowired
  private NativeRegimeService nativeRegime;
  @org.springframework.beans.factory.annotation.Value("${ml.stock-model:native}")
  private String stockModel;

  public ResearchController(
      HistoricalOptimizer optimizer,
      OnnxRegimeService models,
      PerformanceService performance,
      ExternalMarketSyncService market,
      ObjectMapper json) {
    this.optimizer = optimizer;
    this.models = models;
    this.performance = performance;
    this.market = market;
    this.json = json;
  }

  @GetMapping("/models")
  public ApiResponse<Map<String, Object>> models() {
    var result = new LinkedHashMap<String, Object>();
    result.put("models", models.modelStatus());
    result.put("stockEngine", stockModel);
    result.put("goldPrediction", models.predictGoldRegime());
    if ("native".equals(stockModel)) {
      var forecast = nativeRegime.predict();
      result.put("nativeStockPrediction", forecast);
      result.put("stockPrediction", new RegimePrediction(forecast.signal(), 0, forecast.regimeName()));
    } else {
      result.put("stockPrediction", models.predictStockRegime());
    }
    return ApiResponse.success("Trạng thái mô hình", result);
  }

  @GetMapping("/optimize")
  public ApiResponse<Map<String, Object>> optimize(
      @RequestParam List<String> tickers, @RequestParam(defaultValue = "5") double lambda) {
    return ApiResponse.success("Tối ưu từ dữ liệu lịch sử", optimizer.optimize(tickers, lambda));
  }

  @GetMapping("/performance")
  public ApiResponse<Map<String, Object>> performance() {
    return ApiResponse.success(
        "Hiệu suất điều chỉnh dòng tiền",
        performance.report(
            SecurityUtils.getCurrentUserIdOrDefault(null), market.getRiskFreeRate().doubleValue()));
  }

  @GetMapping("/evaluation")
  public ApiResponse<Object> evaluation() throws java.io.IOException {
    var resource = new ClassPathResource("models/stock_regime_report.json");
    if (!resource.exists())
      throw new IllegalStateException(
          "Chưa có báo cáo huấn luyện; chạy python3 ml/train_regime_model.py");
    try (var stream = resource.getInputStream()) {
      return ApiResponse.success(
          "Purged walk-forward và backtest ngoài mẫu", json.readTree(stream));
    }
  }
}
