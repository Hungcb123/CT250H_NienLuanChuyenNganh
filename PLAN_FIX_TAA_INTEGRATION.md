# 🔧 PLAN: Tích Hợp ML ONNX Vào Portfolio Optimizer (Fix TAA)

> **Mục tiêu**: Hiện tại `PortfolioOptimizerService.generateRebalancePlan()` chỉ so sánh tỷ trọng thực tế vs SAA (mỏ neo cố định từ khảo sát). Cần tích hợp `OnnxRegimeService` để tính tỷ trọng TAA (dịch chuyển chiến thuật theo ML) trước khi sinh actions.
>
> **Công thức cốt lõi**: `w_TAA = clamp(w_SAA + Signal × P_confidence × Δw_max, w_SAA - 15%, w_SAA + 15%)`

---

## Tổng Quan Các Task

| # | Task | File chính | Loại |
|:---:|:---|:---|:---|
| 1 | Tạo `RegimePrediction` record | `optimizer/RegimePrediction.java` | **TẠO MỚI** |
| 2 | Tạo `FeatureEngineeringService` | `optimizer/FeatureEngineeringService.java` | **TẠO MỚI** |
| 3 | Nâng cấp `OnnxRegimeService` | `optimizer/OnnxRegimeService.java` | **SỬA** |
| 4 | Mở rộng `RebalancePlanDTO` | `optimizer/RebalancePlanDTO.java` | **SỬA** |
| 5 | Sửa `PortfolioOptimizerService` | `optimizer/PortfolioOptimizerService.java` | **SỬA** |
| 6 | Train `gold_trend.onnx` | `ml/train_regime_model.py` | **SỬA** |
| 7 | Cập nhật Frontend types + TaaTab | `frontend/src/types/index.ts` + `TaaTab.tsx` + `OverviewTab.tsx` | **SỬA** |

---

## TASK 1: Tạo `RegimePrediction` Record

**File**: `/mnt/d/Project_CT250H_NienLuanChuyenNganh/backend/src/main/java/com/equifolio/optimizer/RegimePrediction.java`
**Loại**: TẠO MỚI

### Tại sao cần?
Hiện tại `OnnxRegimeService.predictRegime()` chỉ trả về `int` (signal: -1/0/+1). Nhưng công thức TAA cần cả `signal` VÀ `P_confidence`. Record này đóng gói cả 2 giá trị + tên nhãn để dùng ở nhiều nơi.

### Code hoàn chỉnh:

```java
package com.equifolio.optimizer;

/**
 * Kết quả dự báo từ mô hình ONNX Regime Classification.
 * Chứa cả Signal (hướng) và P_confidence (độ tin cậy) cần thiết cho công thức TAA:
 * Δw = Signal × P_confidence × Δw_max
 */
public record RegimePrediction(
        int signal,            // -1 (Bearish), 0 (Sideway), +1 (Bullish)
        double confidence,     // Xác suất của nhãn thắng thế (0.0 → 1.0)
        String regimeName      // Tên nhãn đọc được: "BULLISH", "SIDEWAY", "BEARISH"
) {

    /**
     * Tạo prediction mặc định khi không có model hoặc lỗi inference.
     * Signal = 0 (Sideway) với confidence = 0.33 → Δw ≈ 0 → giữ nguyên SAA.
     */
    public static RegimePrediction neutral() {
        return new RegimePrediction(0, 0.33, "SIDEWAY_NEUTRAL");
    }

    /**
     * Tạo prediction từ signal int với confidence mặc định 0.60 (cho fallback heuristic).
     */
    public static RegimePrediction fromSignal(int signal) {
        String name = switch (signal) {
            case 1 -> "BULLISH_UPTREND";
            case -1 -> "BEARISH_DOWNTREND";
            default -> "SIDEWAY_ACCUMULATION";
        };
        return new RegimePrediction(signal, 0.60, name);
    }
}
```

### Acceptance Criteria:
- [ ] File tồn tại tại đường dẫn trên
- [ ] Có `neutral()` factory method
- [ ] Có `fromSignal(int)` factory method
- [ ] Package đúng `com.equifolio.optimizer`

---

## TASK 2: Tạo `FeatureEngineeringService`

**File**: `/mnt/d/Project_CT250H_NienLuanChuyenNganh/backend/src/main/java/com/equifolio/optimizer/FeatureEngineeringService.java`
**Loại**: TẠO MỚI

### Tại sao cần?
Hiện tại `OnnxRegimeService.getLatestRegimeName()` dùng features hardcode. Để ONNX dự báo chính xác, cần tính features từ dữ liệu giá thật trong bảng `market_prices`. Service này query 60 ngày gần nhất từ DB, tính RSI/MACD/BB/SMA/ATR/ROC/Volume Ratio/HV, trả về `float[]` đúng format cho ONNX.

### Dependency:
- Cần inject `MarketPriceRepository` (đã có sẵn, import từ `com.equifolio.market.MarketPriceRepository`)
- Dùng query `findByAsset_TickerOrderByTradeDateAsc(String ticker)` đã có sẵn trong repo

### Code hoàn chỉnh:

```java
package com.equifolio.optimizer;

import com.equifolio.market.MarketPrice;
import com.equifolio.market.MarketPriceRepository;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;

/**
 * Tính toán các chỉ báo kỹ thuật (Technical Indicators) từ dữ liệu giá lịch sử
 * trong bảng market_prices. Xuất ra float[] đúng format cho ONNX model inference.
 *
 * Danh sách 14 features (khớp với train_regime_model.py):
 * [0]  RSI_14
 * [1]  MFI_14 (dùng RSI thay thế vì không có volume chi tiết)
 * [2]  MACD (normalized by price)
 * [3]  MACD_Signal
 * [4]  MACD_Hist
 * [5]  BB_Width
 * [6]  BB_PctB
 * [7]  SMA_20_50_Ratio
 * [8]  Dist_SMA20 (distance from SMA20, normalized)
 * [9]  Dist_SMA50 (distance from SMA50, normalized)
 * [10] ATR_Pct
 * [11] ROC_20
 * [12] Volume_Ratio (default 1.0 nếu không có volume)
 * [13] HV_20 (Historical Volatility 20 ngày)
 */
@Service
public class FeatureEngineeringService {

    private final MarketPriceRepository marketPriceRepository;

    public FeatureEngineeringService(MarketPriceRepository marketPriceRepository) {
        this.marketPriceRepository = marketPriceRepository;
    }

    /**
     * Tính 14 technical features cho một ticker từ market_prices trong DB.
     * Cần tối thiểu 60 phiên dữ liệu giá để tính đủ các chỉ báo.
     *
     * @param ticker Mã tài sản (VD: "VNINDEX" cho cổ phiếu, "GOLD_SJC" cho vàng)
     * @return float[14] features, hoặc null nếu không đủ dữ liệu
     */
    public float[] calculateFeatures(String ticker) {
        List<MarketPrice> prices = marketPriceRepository.findByAsset_TickerOrderByTradeDateAsc(ticker);

        // Cần tối thiểu 60 phiên để tính SMA50 + buffer
        if (prices == null || prices.size() < 60) {
            return null;
        }

        // Chỉ lấy 120 phiên gần nhất để tính toán (tiết kiệm bộ nhớ)
        int startIdx = Math.max(0, prices.size() - 120);
        List<MarketPrice> recent = prices.subList(startIdx, prices.size());

        double[] closes = recent.stream()
                .mapToDouble(p -> p.getPrice().doubleValue())
                .toArray();
        int n = closes.length;

        // 1. RSI(14)
        double rsi = calculateRSI(closes, 14);

        // 2. MACD(12,26,9) normalized by price
        double[] ema12 = ema(closes, 12);
        double[] ema26 = ema(closes, 26);
        double lastPrice = closes[n - 1];
        double macd = (ema12[n - 1] - ema26[n - 1]) / lastPrice * 100.0;

        double[] macdLine = new double[n];
        for (int i = 0; i < n; i++) {
            macdLine[i] = (ema12[i] - ema26[i]) / (closes[i] == 0 ? 1 : closes[i]) * 100.0;
        }
        double[] macdSignalArr = ema(macdLine, 9);
        double macdSignal = macdSignalArr[n - 1];
        double macdHist = macd - macdSignal;

        // 3. Bollinger Bands(20, 2)
        double sma20 = sma(closes, 20);
        double std20 = rollingStd(closes, 20);
        double upperBand = sma20 + 2 * std20;
        double lowerBand = sma20 - 2 * std20;
        double bbWidth = (upperBand - lowerBand) / (sma20 == 0 ? 1 : sma20);
        double bbPctB = (upperBand == lowerBand) ? 0.5 :
                (lastPrice - lowerBand) / (upperBand - lowerBand);

        // 4. SMA Ratio (20/50)
        double sma50 = sma(closes, 50);
        double smaRatio = (sma50 == 0) ? 1.0 : sma20 / sma50;

        // 5. Distance from SMA20, SMA50
        double distSma20 = (sma20 == 0) ? 0 : (lastPrice - sma20) / sma20;
        double distSma50 = (sma50 == 0) ? 0 : (lastPrice - sma50) / sma50;

        // 6. ATR%(14) — Simplified (High-Low approx = price * 0.02 nếu ko có OHLC)
        // Vì MarketPrice chỉ có price (close), dùng rolling range proxy
        double atrPct = calculateApproxATR(closes, 14);

        // 7. ROC(20) — Rate of Change
        double roc20 = (n >= 21 && closes[n - 21] != 0)
                ? (lastPrice / closes[n - 21] - 1.0) * 100.0
                : 0.0;

        // 8. Volume Ratio — MarketPrice không có volume → default 1.0
        double volumeRatio = 1.0;

        // 9. Historical Volatility 20D (annualized)
        double hv20 = calculateHV(closes, 20);

        return new float[]{
                (float) rsi,          // [0] RSI_14
                (float) rsi,          // [1] MFI_14 (proxy = RSI)
                (float) macd,         // [2] MACD
                (float) macdSignal,   // [3] MACD_Signal
                (float) macdHist,     // [4] MACD_Hist
                (float) bbWidth,      // [5] BB_Width
                (float) bbPctB,       // [6] BB_PctB
                (float) smaRatio,     // [7] SMA_20_50_Ratio
                (float) distSma20,    // [8] Dist_SMA20
                (float) distSma50,    // [9] Dist_SMA50
                (float) atrPct,       // [10] ATR_Pct
                (float) roc20,        // [11] ROC_20
                (float) volumeRatio,  // [12] Volume_Ratio
                (float) hv20          // [13] HV_20
        };
    }

    // ──── HELPER METHODS ────

    private double calculateRSI(double[] prices, int period) {
        if (prices.length < period + 1) return 50.0;
        double gainSum = 0, lossSum = 0;
        for (int i = prices.length - period; i < prices.length; i++) {
            double change = prices[i] - prices[i - 1];
            if (change > 0) gainSum += change;
            else lossSum += Math.abs(change);
        }
        double avgGain = gainSum / period;
        double avgLoss = lossSum / period;
        if (avgLoss == 0) return 100.0;
        double rs = avgGain / avgLoss;
        return 100.0 - (100.0 / (1.0 + rs));
    }

    private double[] ema(double[] data, int period) {
        double[] result = new double[data.length];
        double multiplier = 2.0 / (period + 1);
        result[0] = data[0];
        for (int i = 1; i < data.length; i++) {
            result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1];
        }
        return result;
    }

    private double sma(double[] prices, int period) {
        if (prices.length < period) return prices[prices.length - 1];
        double sum = 0;
        for (int i = prices.length - period; i < prices.length; i++) {
            sum += prices[i];
        }
        return sum / period;
    }

    private double rollingStd(double[] prices, int period) {
        if (prices.length < period) return 0;
        double mean = sma(prices, period);
        double sumSq = 0;
        for (int i = prices.length - period; i < prices.length; i++) {
            sumSq += (prices[i] - mean) * (prices[i] - mean);
        }
        return Math.sqrt(sumSq / period);
    }

    private double calculateApproxATR(double[] closes, int period) {
        // Approximate ATR using absolute daily returns when OHLC not available
        if (closes.length < period + 1) return 0;
        double sum = 0;
        for (int i = closes.length - period; i < closes.length; i++) {
            sum += Math.abs(closes[i] - closes[i - 1]);
        }
        double atr = sum / period;
        double lastPrice = closes[closes.length - 1];
        return (lastPrice == 0) ? 0 : (atr / lastPrice) * 100.0;
    }

    private double calculateHV(double[] closes, int period) {
        if (closes.length < period + 1) return 0;
        double[] logReturns = new double[period];
        for (int i = 0; i < period; i++) {
            int idx = closes.length - period + i;
            logReturns[i] = Math.log(closes[idx] / closes[idx - 1]);
        }
        double mean = 0;
        for (double lr : logReturns) mean += lr;
        mean /= period;
        double sumSq = 0;
        for (double lr : logReturns) sumSq += (lr - mean) * (lr - mean);
        double dailyVol = Math.sqrt(sumSq / (period - 1));
        return dailyVol * Math.sqrt(252) * 100.0; // Annualized
    }
}
```

### Acceptance Criteria:
- [ ] File tồn tại tại đường dẫn trên
- [ ] `calculateFeatures("VNINDEX")` trả về `float[14]` hoặc `null`
- [ ] Trả `null` khi ít hơn 60 phiên dữ liệu
- [ ] Các hàm helper: `calculateRSI`, `ema`, `sma`, `rollingStd`, `calculateApproxATR`, `calculateHV` đều private

---

## TASK 3: Nâng Cấp `OnnxRegimeService`

**File**: `/mnt/d/Project_CT250H_NienLuanChuyenNganh/backend/src/main/java/com/equifolio/optimizer/OnnxRegimeService.java`
**Loại**: SỬA FILE CÓ SẴN

### Tại sao cần sửa?
1. Hiện chỉ load `stock_regime.onnx`, cần thêm `gold_trend.onnx`
2. `predictRegime()` chỉ trả `int`, cần method mới `predictWithConfidence()` trả `RegimePrediction` (gồm cả `signal` + `confidence`)
3. Hiện ONNX session chỉ lấy label (output 0), cần lấy thêm probabilities (output 1) để có `P_confidence`
4. Cần inject `FeatureEngineeringService` để tự tính features thay vì hardcode

### Thay đổi cần làm:

#### 3a. Thêm field cho gold model + FeatureEngineeringService

Tìm đoạn code này (khoảng dòng 21-27):
```java
@Service
public class OnnxRegimeService {

    private static final Logger log = LoggerFactory.getLogger(OnnxRegimeService.class);

    private OrtEnvironment env;
    private OrtSession session;
    private boolean modelLoaded = false;
```

**Sửa thành:**
```java
@Service
public class OnnxRegimeService {

    private static final Logger log = LoggerFactory.getLogger(OnnxRegimeService.class);

    private final FeatureEngineeringService featureService;

    private OrtEnvironment env;

    // Stock regime model
    private OrtSession stockSession;
    private boolean stockModelLoaded = false;

    // Gold trend model
    private OrtSession goldSession;
    private boolean goldModelLoaded = false;

    public OnnxRegimeService(FeatureEngineeringService featureService) {
        this.featureService = featureService;
    }
```

#### 3b. Sửa `@PostConstruct init()` để load cả 2 model

Tìm method `init()` (khoảng dòng 29-47) và **thay toàn bộ** bằng:
```java
    @PostConstruct
    public void init() {
        env = OrtEnvironment.getEnvironment();

        // Load Stock Regime Model
        stockSession = loadModel("models/stock_regime.onnx");
        stockModelLoaded = (stockSession != null);
        if (stockModelLoaded) {
            log.info("✅ Loaded ONNX Stock Regime model successfully.");
        } else {
            log.warn("⚠️ stock_regime.onnx not found. Stock inference will use heuristic fallback.");
        }

        // Load Gold Trend Model
        goldSession = loadModel("models/gold_trend.onnx");
        goldModelLoaded = (goldSession != null);
        if (goldModelLoaded) {
            log.info("✅ Loaded ONNX Gold Trend model successfully.");
        } else {
            log.warn("⚠️ gold_trend.onnx not found. Gold inference will use heuristic fallback.");
        }
    }

    private OrtSession loadModel(String classpathResource) {
        try {
            ClassPathResource resource = new ClassPathResource(classpathResource);
            if (resource.exists()) {
                try (InputStream is = resource.getInputStream()) {
                    byte[] modelBytes = is.readAllBytes();
                    return env.createSession(modelBytes, new OrtSession.SessionOptions());
                }
            }
        } catch (Exception e) {
            log.warn("Failed to load ONNX model {}: {}", classpathResource, e.getMessage());
        }
        return null;
    }
```

#### 3c. Thêm method `predictWithConfidence()` — ĐÂY LÀ METHOD QUAN TRỌNG NHẤT

Thêm method mới **ngay sau** method `predictRegime()` hiện có (GIỮA NGUYÊN `predictRegime`, chỉ thêm method mới):

```java
    /**
     * Dự báo regime KÈM xác suất tin cậy cho Optimizer TAA.
     * Đọc output thứ 2 (probabilities) từ ONNX model.
     *
     * @param features float[] technical indicators
     * @param session  OrtSession tương ứng (stock hoặc gold)
     * @param loaded   boolean model đã load chưa
     * @return RegimePrediction(signal, confidence, name)
     */
    private RegimePrediction predictWithConfidenceInternal(float[] features, OrtSession session, boolean loaded) {
        if (!loaded || session == null || features == null) {
            return RegimePrediction.fromSignal(fallbackHeuristic(features));
        }

        try {
            float[] inputFeatures = features;
            if (inputFeatures.length < 14) {
                inputFeatures = new float[14];
                System.arraycopy(features, 0, inputFeatures, 0, features.length);
            }

            long[] shape = new long[]{1, inputFeatures.length};
            FloatBuffer buffer = FloatBuffer.wrap(inputFeatures);
            OnnxTensor tensor = OnnxTensor.createTensor(env, buffer, shape);

            try (OrtSession.Result result = session.run(Collections.singletonMap("float_input", tensor))) {
                int signal = 0;
                double confidence = 0.33;

                // Output 0: Label (long[])
                if (result.size() > 0) {
                    OnnxValue labelVal = result.get(0);
                    if (labelVal != null && labelVal.getValue() instanceof long[] labels) {
                        signal = (int) labels[0] - 1; // 0→-1, 1→0, 2→+1
                    }
                }

                // Output 1: Probabilities (List<Map<Long, Float>>)
                // LightGBM ONNX models output probabilities as the second output
                if (result.size() > 1) {
                    OnnxValue probVal = result.get(1);
                    if (probVal != null) {
                        try {
                            // LightGBM outputs [{0: p0, 1: p1, 2: p2}]
                            @SuppressWarnings("unchecked")
                            List<Map<Long, Float>> probMaps = (List<Map<Long, Float>>) probVal.getValue();
                            if (probMaps != null && !probMaps.isEmpty()) {
                                Map<Long, Float> probs = probMaps.get(0);
                                long winningClass = signal + 1; // convert back: -1→0, 0→1, +1→2
                                Float prob = probs.get(winningClass);
                                if (prob != null) {
                                    confidence = prob.doubleValue();
                                }
                            }
                        } catch (Exception e) {
                            log.debug("Could not extract probabilities, using default confidence: {}", e.getMessage());
                        }
                    }
                }

                String name = switch (signal) {
                    case 1 -> "BULLISH_UPTREND";
                    case -1 -> "BEARISH_DOWNTREND";
                    default -> "SIDEWAY_ACCUMULATION";
                };

                return new RegimePrediction(signal, confidence, name);
            }
        } catch (Exception e) {
            log.error("ONNX inference error: {}. Falling back.", e.getMessage());
        }

        return RegimePrediction.fromSignal(fallbackHeuristic(features));
    }

    /**
     * Dự báo trạng thái thị trường CỔ PHIẾU T+20 kèm confidence.
     * Dùng features tự tính từ market_prices nếu có, fallback sang features mẫu.
     */
    public RegimePrediction predictStockRegime() {
        float[] features = featureService.calculateFeatures("VNINDEX");
        if (features == null) {
            // Fallback: thử với ticker VN30 ETF hoặc dùng sample features
            features = featureService.calculateFeatures("E1VFVN30");
        }
        if (features == null) {
            log.warn("Not enough market data for stock features. Using neutral prediction.");
            return RegimePrediction.neutral();
        }
        return predictWithConfidenceInternal(features, stockSession, stockModelLoaded);
    }

    /**
     * Dự báo trạng thái thị trường VÀNG T+20 kèm confidence.
     */
    public RegimePrediction predictGoldRegime() {
        float[] features = featureService.calculateFeatures("GOLD_SJC");
        if (features == null) {
            features = featureService.calculateFeatures("GC");
        }
        if (features == null) {
            log.warn("Not enough market data for gold features. Using neutral prediction.");
            return RegimePrediction.neutral();
        }
        return predictWithConfidenceInternal(features, goldSession, goldModelLoaded);
    }
```

#### 3d. Sửa method `predictRegime()` hiện có để dùng `stockSession`

Tìm dòng này trong `predictRegime()`:
```java
        if (!modelLoaded || session == null) {
```
**Sửa thành:**
```java
        if (!stockModelLoaded || stockSession == null) {
```

Tìm dòng này:
```java
            try (OrtSession.Result result = session.run(Collections.singletonMap("float_input", tensor))) {
```
**Sửa thành:**
```java
            try (OrtSession.Result result = stockSession.run(Collections.singletonMap("float_input", tensor))) {
```

#### 3e. Sửa method `getLatestRegimeName()` để dùng method mới

Tìm method `getLatestRegimeName()` (khoảng dòng 102-125) và **thay toàn bộ**:
```java
    public String getLatestRegimeName() {
        RegimePrediction prediction = predictStockRegime();
        return prediction.regimeName() + " (Độ tin cậy: " +
                String.format("%.0f%%", prediction.confidence() * 100) + ")";
    }
```

#### 3f. Sửa `@PreDestroy cleanup()` để đóng cả 2 session

Tìm method `cleanup()` và **thay toàn bộ**:
```java
    @PreDestroy
    public void cleanup() {
        try {
            if (stockSession != null) stockSession.close();
            if (goldSession != null) goldSession.close();
            if (env != null) env.close();
        } catch (Exception e) {
            log.error("Error closing ONNX sessions: {}", e.getMessage());
        }
    }
```

### Acceptance Criteria:
- [ ] Load 2 model: `stock_regime.onnx` + `gold_trend.onnx`
- [ ] `predictStockRegime()` trả về `RegimePrediction` cho cổ phiếu
- [ ] `predictGoldRegime()` trả về `RegimePrediction` cho vàng
- [ ] `predictRegime(float[])` vẫn hoạt động (backward compat cho CopilotService)
- [ ] `getLatestRegimeName()` vẫn hoạt động (backward compat cho CopilotService)
- [ ] Không cần thay đổi bất kỳ thứ gì trong `CopilotService.java`

---

## TASK 4: Mở Rộng `RebalancePlanDTO`

**File**: `/mnt/d/Project_CT250H_NienLuanChuyenNganh/backend/src/main/java/com/equifolio/optimizer/RebalancePlanDTO.java`
**Loại**: SỬA FILE CÓ SẴN

### Tại sao cần?
Hiện DTO chỉ có `targetAllocations` (chính là SAA). Cần tách thành `saaTargets` + `taaTargets` + thêm `mlPredictions` để Frontend biết ML dự báo gì, SAA gốc bao nhiêu, TAA sau adjust bao nhiêu.

### Thay đổi cần làm:

#### 4a. Thêm 3 field mới VÀ inner class `MlPredictionInfo`

Tìm đoạn khai báo fields (khoảng dòng 9-20):
```java
public class RebalancePlanDTO {
    private boolean driftDetected;
    private BigDecimal maxDriftPercent;
    private Map<String, BigDecimal> currentAllocations = new HashMap<>();
    private Map<String, BigDecimal> targetAllocations = new HashMap<>();
    private List<RebalanceAction> actions = new ArrayList<>();
    private String executiveSummary;
    ...
```

**Thêm ngay SAU dòng `targetAllocations`:**
```java
    // ── TAA fields mới ──
    private Map<String, BigDecimal> saaTargets = new HashMap<>();       // Tỷ trọng mỏ neo SAA (từ khảo sát)
    private Map<String, BigDecimal> taaTargets = new HashMap<>();       // Tỷ trọng sau ML adjust
    private List<MlPredictionInfo> mlPredictions = new ArrayList<>();   // Chi tiết dự báo ML
```

#### 4b. Thêm inner class `MlPredictionInfo` ngay SAU inner class `RebalanceAction`

Thêm SAU dấu `}` đóng của class `RebalanceAction` (khoảng dòng 87):

```java
    /**
     * Thông tin dự báo ML cho một lớp tài sản.
     */
    public static class MlPredictionInfo {
        private String assetClass;    // "STOCK" hoặc "GOLD"
        private String modelName;     // "stock_regime.onnx" hoặc "gold_trend.onnx"
        private int signal;           // -1, 0, +1
        private double confidence;    // 0.0 → 1.0
        private String regimeName;    // "BULLISH_UPTREND", etc.
        private BigDecimal deltaWeight; // Δw = Signal × P × 15%

        public MlPredictionInfo() {}

        public MlPredictionInfo(String assetClass, String modelName, int signal,
                                double confidence, String regimeName, BigDecimal deltaWeight) {
            this.assetClass = assetClass;
            this.modelName = modelName;
            this.signal = signal;
            this.confidence = confidence;
            this.regimeName = regimeName;
            this.deltaWeight = deltaWeight;
        }

        public String getAssetClass() { return assetClass; }
        public void setAssetClass(String assetClass) { this.assetClass = assetClass; }

        public String getModelName() { return modelName; }
        public void setModelName(String modelName) { this.modelName = modelName; }

        public int getSignal() { return signal; }
        public void setSignal(int signal) { this.signal = signal; }

        public double getConfidence() { return confidence; }
        public void setConfidence(double confidence) { this.confidence = confidence; }

        public String getRegimeName() { return regimeName; }
        public void setRegimeName(String regimeName) { this.regimeName = regimeName; }

        public BigDecimal getDeltaWeight() { return deltaWeight; }
        public void setDeltaWeight(BigDecimal deltaWeight) { this.deltaWeight = deltaWeight; }
    }
```

#### 4c. Thêm getters/setters cho 3 field mới

Thêm vào cuối file, **trước dấu `}` đóng class**:

```java
    public Map<String, BigDecimal> getSaaTargets() { return saaTargets; }
    public void setSaaTargets(Map<String, BigDecimal> saaTargets) { this.saaTargets = saaTargets; }

    public Map<String, BigDecimal> getTaaTargets() { return taaTargets; }
    public void setTaaTargets(Map<String, BigDecimal> taaTargets) { this.taaTargets = taaTargets; }

    public List<MlPredictionInfo> getMlPredictions() { return mlPredictions; }
    public void setMlPredictions(List<MlPredictionInfo> mlPredictions) { this.mlPredictions = mlPredictions; }
```

### QUAN TRỌNG:
- **GIỮA NGUYÊN** field `targetAllocations` + getter/setter của nó. Đừng xóa. Frontend cũ vẫn đọc field này.
- Sau khi sửa Task 5, `targetAllocations` sẽ chứa giá trị TAA (thay vì SAA như hiện tại).

### Acceptance Criteria:
- [ ] Có field `saaTargets`, `taaTargets`, `mlPredictions`
- [ ] Có inner class `MlPredictionInfo` với đầy đủ getters/setters
- [ ] `targetAllocations` VẪN CÒN (backward compat)

---

## TASK 5: Sửa `PortfolioOptimizerService.generateRebalancePlan()`

**File**: `/mnt/d/Project_CT250H_NienLuanChuyenNganh/backend/src/main/java/com/equifolio/optimizer/PortfolioOptimizerService.java`
**Loại**: SỬA FILE CÓ SẴN — **ĐÂY LÀ TASK QUAN TRỌNG NHẤT**

### Tại sao cần?
Đây là nơi logic TAA cần được tích hợp. Hiện tại method `generateRebalancePlan()` đọc `portfolio_targets` (SAA) rồi so sánh trực tiếp với `currentAllocations`. Cần thêm bước:
1. Gọi `OnnxRegimeService.predictStockRegime()` + `predictGoldRegime()`
2. Tính `Δw = Signal × P_confidence × 0.15` cho mỗi asset class
3. `w_TAA = clamp(w_SAA + Δw, w_SAA - 0.15, w_SAA + 0.15)`
4. Normalize để `Σ w_TAA = 1.0`
5. Dùng `w_TAA` (thay vì `w_SAA`) làm target khi tính actions

### Thay đổi cần làm:

#### 5a. Inject `OnnxRegimeService` vào constructor

Tìm khai báo fields (dòng 21-27):
```java
    private final LedgerService ledgerService;
    private final PortfolioTargetRepository portfolioTargetRepository;
    private final MarketService marketService;
    private final AccountRepository accountRepository;
    private final TransactionRepository transactionRepository;
    private final UserRepository userRepository;
    private final AssetRepository assetRepository;
```

**Thêm 1 dòng:**
```java
    private final OnnxRegimeService onnxRegimeService;
```

Tìm constructor (dòng 29-43), **thêm parameter `OnnxRegimeService onnxRegimeService`** và gán `this.onnxRegimeService = onnxRegimeService;`

Constructor sửa lại:
```java
    public PortfolioOptimizerService(LedgerService ledgerService,
                                     PortfolioTargetRepository portfolioTargetRepository,
                                     MarketService marketService,
                                     AccountRepository accountRepository,
                                     TransactionRepository transactionRepository,
                                     UserRepository userRepository,
                                     AssetRepository assetRepository,
                                     OnnxRegimeService onnxRegimeService) {
        this.ledgerService = ledgerService;
        this.portfolioTargetRepository = portfolioTargetRepository;
        this.marketService = marketService;
        this.accountRepository = accountRepository;
        this.transactionRepository = transactionRepository;
        this.userRepository = userRepository;
        this.assetRepository = assetRepository;
        this.onnxRegimeService = onnxRegimeService;
    }
```

#### 5b. Thêm constant và helper method

Thêm **ngay sau constructor**, trước method `generateRebalancePlan()`:

```java
    /** Biên độ dịch chuyển tối đa TAA: ±15% quanh SAA */
    private static final BigDecimal DELTA_W_MAX = new BigDecimal("0.15");

    /** Biên độ dịch chuyển tối đa cho Vàng: ±10% (thận trọng hơn cổ phiếu) */
    private static final BigDecimal DELTA_W_MAX_GOLD = new BigDecimal("0.10");

    /**
     * Tính tỷ trọng TAA cho một lớp tài sản:
     * w_TAA = clamp(w_SAA + Δw, w_SAA - deltaMax, w_SAA + deltaMax)
     * Trong đó: Δw = signal × confidence × deltaMax
     */
    private BigDecimal calculateTaaWeight(BigDecimal saaw, RegimePrediction prediction, BigDecimal deltaMax) {
        BigDecimal delta = deltaMax
                .multiply(BigDecimal.valueOf(prediction.signal()))
                .multiply(BigDecimal.valueOf(prediction.confidence()))
                .setScale(4, RoundingMode.HALF_EVEN);

        BigDecimal taaRaw = saaw.add(delta);
        BigDecimal lower = saaw.subtract(deltaMax).max(BigDecimal.ZERO);
        BigDecimal upper = saaw.add(deltaMax).min(BigDecimal.ONE);

        return taaRaw.max(lower).min(upper).setScale(4, RoundingMode.HALF_EVEN);
    }
```

#### 5c. Sửa method `generateRebalancePlan()` — PHẦN CHÍNH

Trong method `generateRebalancePlan()`, tìm đoạn code này (khoảng dòng 49-56):
```java
        Map<String, BigDecimal> targetMap = new HashMap<>();
        for (PortfolioTarget t : targets) {
            targetMap.put(t.getAssetClass(), t.getTargetWeight());
        }
        plan.setTargetAllocations(targetMap);
```

**THAY TOÀN BỘ ĐOẠN ĐÓ** bằng:
```java
        // ═══ SAA: Đọc tỷ trọng mỏ neo (cố định từ khảo sát) ═══
        Map<String, BigDecimal> saaMap = new HashMap<>();
        for (PortfolioTarget t : targets) {
            saaMap.put(t.getAssetClass(), t.getTargetWeight());
        }
        plan.setSaaTargets(new HashMap<>(saaMap));

        // ═══ ML: Gọi ONNX dự báo regime T+20 ═══
        RegimePrediction stockPrediction = onnxRegimeService.predictStockRegime();
        RegimePrediction goldPrediction = onnxRegimeService.predictGoldRegime();

        // ═══ TAA: Dịch chuyển tỷ trọng theo ML ═══
        BigDecimal saawStock = saaMap.getOrDefault("STOCK", new BigDecimal("0.35"));
        BigDecimal saawGold = saaMap.getOrDefault("GOLD", new BigDecimal("0.35"));

        BigDecimal taawStock = calculateTaaWeight(saawStock, stockPrediction, DELTA_W_MAX);
        BigDecimal taawGold = calculateTaaWeight(saawGold, goldPrediction, DELTA_W_MAX_GOLD);

        // Phần còn lại (CASH_SAVINGS) = 1.0 - STOCK - GOLD
        BigDecimal taawCashSavings = BigDecimal.ONE.subtract(taawStock).subtract(taawGold)
                .max(BigDecimal.ZERO).setScale(4, RoundingMode.HALF_EVEN);

        // Phân chia CASH_SAVINGS thành SAVINGS và CASH theo tỷ lệ SAA gốc
        BigDecimal saawSavings = saaMap.getOrDefault("SAVINGS", new BigDecimal("0.20"));
        BigDecimal saawCash = saaMap.getOrDefault("CASH", new BigDecimal("0.10"));
        BigDecimal cashSavingsTotal = saawSavings.add(saawCash);
        BigDecimal savingsRatio = (cashSavingsTotal.compareTo(BigDecimal.ZERO) > 0)
                ? saawSavings.divide(cashSavingsTotal, 4, RoundingMode.HALF_EVEN)
                : new BigDecimal("0.6667");
        BigDecimal taawSavings = taawCashSavings.multiply(savingsRatio).setScale(4, RoundingMode.HALF_EVEN);
        BigDecimal taawCash = taawCashSavings.subtract(taawSavings);

        // Build TAA target map
        Map<String, BigDecimal> taaMap = new HashMap<>();
        taaMap.put("STOCK", taawStock);
        taaMap.put("GOLD", taawGold);
        taaMap.put("SAVINGS", taawSavings);
        taaMap.put("CASH", taawCash);
        taaMap.put("CASH_SAVINGS", taawCashSavings);

        plan.setTaaTargets(new HashMap<>(taaMap));

        // targetAllocations = TAA targets (for backward compat — Frontend reads this field)
        plan.setTargetAllocations(taaMap);

        // ═══ ML Predictions info ═══
        BigDecimal stockDelta = taawStock.subtract(saawStock);
        BigDecimal goldDelta = taawGold.subtract(saawGold);

        List<RebalancePlanDTO.MlPredictionInfo> mlInfoList = new ArrayList<>();
        mlInfoList.add(new RebalancePlanDTO.MlPredictionInfo(
                "STOCK", "stock_regime.onnx",
                stockPrediction.signal(), stockPrediction.confidence(),
                stockPrediction.regimeName(), stockDelta));
        mlInfoList.add(new RebalancePlanDTO.MlPredictionInfo(
                "GOLD", "gold_trend.onnx",
                goldPrediction.signal(), goldPrediction.confidence(),
                goldPrediction.regimeName(), goldDelta));
        plan.setMlPredictions(mlInfoList);

        // ═══ Tiếp tục dùng taaMap (thay vì saaMap) cho Drift Detection & Actions ═══
        Map<String, BigDecimal> targetMap = taaMap;
```

> [!CAUTION]
> Biến `targetMap` giờ trỏ tới `taaMap`. Toàn bộ code phía dưới (drift detection, SELL/BUY actions) vẫn dùng biến `targetMap` → tự động dùng tỷ trọng TAA. **KHÔNG CẦN SỬA GÌ THÊM** phía dưới.

#### 5d. Sửa `executiveSummary` để mention ML

Tìm đoạn tạo executiveSummary (khoảng dòng 257-261):
```java
        if (isDrift) {
            plan.setExecutiveSummary("Phát hiện tỷ trọng danh mục lệch " + plan.getMaxDriftPercent() + "% so với mục tiêu SAA. Đề xuất thực hiện các lệnh điều chỉnh lô chẵn bên dưới để đưa danh mục về vùng cân bằng tối ưu.");
```

**Sửa thành:**
```java
        if (isDrift) {
            plan.setExecutiveSummary("Phát hiện tỷ trọng danh mục lệch " + plan.getMaxDriftPercent() +
                    "% so với mục tiêu TAA (đã điều chỉnh theo tín hiệu ML: Cổ phiếu " +
                    stockPrediction.regimeName() + " " + String.format("%.0f%%", stockPrediction.confidence() * 100) +
                    ", Vàng " + goldPrediction.regimeName() + " " + String.format("%.0f%%", goldPrediction.confidence() * 100) +
                    "). Đề xuất thực hiện các lệnh điều chỉnh lô chẵn bên dưới.");
```

### Acceptance Criteria:
- [ ] `OnnxRegimeService` được inject qua constructor
- [ ] `generateRebalancePlan()` gọi `predictStockRegime()` + `predictGoldRegime()`
- [ ] `taaTargets` được tính bằng công thức `w_SAA + Signal × P × Δw_max` rồi clamp
- [ ] `targetAllocations` chứa giá trị TAA (backward compat)
- [ ] `saaTargets` chứa giá trị SAA gốc
- [ ] `mlPredictions` chứa info ML cho cả STOCK và GOLD
- [ ] `executiveSummary` mention tín hiệu ML
- [ ] `executeRebalancePlan()` KHÔNG CẦN SỬA (nó gọi `generateRebalancePlan()` nội bộ)

---

## TASK 6: Train `gold_trend.onnx`

**File**: `/mnt/d/Project_CT250H_NienLuanChuyenNganh/ml/train_regime_model.py`
**Loại**: SỬA (thêm function train gold model)

### Tại sao cần?
Hiện script chỉ train `stock_regime.onnx`. Cần thêm function train `gold_trend.onnx` từ dữ liệu vàng.

### Thay đổi cần làm:

#### 6a. Thêm function `train_gold_model()` TRƯỚC `if __name__ == '__main__':`

```python
def train_gold_model(output_dir: str = "backend/src/main/resources/models"):
    """
    Trains Gold Trend Classifier (T+20) using Gold price data.
    Labels: 0=Bearish (<-3%), 1=Sideway, 2=Bullish (>+3%).
    Exports to gold_trend.onnx.
    """
    print("=== Training Gold Trend Model ===")
    
    # Load gold data
    gold_path = "ml/data/raw/GC.csv"
    if not os.path.exists(gold_path):
        print(f"⚠️ Gold data not found at {gold_path}. Run fetch_market_data.py first.")
        print("Falling back to synthetic gold data...")
        days = 1500
        dates = pd.date_range(end=pd.Timestamp.today(), periods=days, freq='B')
        gold_returns = np.random.normal(0.0003, 0.012, days)
        gold_price = 1800.0 * np.cumprod(1 + gold_returns)
        df_gold = pd.DataFrame({
            'Date': dates,
            'Open': gold_price * 0.998,
            'High': gold_price * 1.008,
            'Low': gold_price * 0.992,
            'Close': gold_price,
            'Volume': np.random.lognormal(12.0, 0.5, days),
            'Gold_Close': gold_price  # Self-reference for gold
        })
    else:
        print(f"🥇 Loading real Gold data from: {gold_path}")
        df_gold = pd.read_csv(gold_path)
        df_gold['Date'] = pd.to_datetime(df_gold['Date'])
        df_gold = df_gold.sort_values('Date').reset_index(drop=True)
        df_gold['Gold_Close'] = df_gold['Close']  # Self-reference

    df_features, feature_cols = calculate_technical_features(df_gold)
    dataset = create_regime_labels(df_features, horizon=20, threshold=0.03)

    X = dataset[feature_cols].values.astype(np.float32)
    y = dataset['Target_Regime'].values.astype(np.int64)

    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"Gold samples: {len(dataset)} | Train: {len(X_train)} | Test: {len(X_test)}")

    model = LGBMClassifier(
        n_estimators=100,
        learning_rate=0.04,
        max_depth=4,
        num_leaves=16,
        min_child_samples=20,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        class_weight='balanced',
        verbose=-1
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n--- Gold Model Out-of-Sample Evaluation ---")
    print(classification_report(y_test, y_pred, target_names=['Bearish', 'Sideway', 'Bullish']))
    print(f"F1-Macro: {f1_score(y_test, y_pred, average='macro'):.4f}")

    os.makedirs(output_dir, exist_ok=True)
    onnx_path = os.path.join(output_dir, "gold_trend.onnx")
    initial_type = [('float_input', FloatTensorType([None, len(feature_cols)]))]
    onnx_model = onnxmltools.convert_lightgbm(model, initial_types=initial_type, target_opset=15)

    with open(onnx_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    print(f"✅ Gold ONNX model saved to: {onnx_path}")
    print(f"📦 File size: {os.path.getsize(onnx_path) / 1024:.2f} KB")
```

#### 6b. Sửa `if __name__ == '__main__':` để train cả 2 model

```python
if __name__ == '__main__':
    train_and_export_onnx()     # Stock model
    train_gold_model()          # Gold model
```

#### 6c. Chạy script

```bash
cd /mnt/d/Project_CT250H_NienLuanChuyenNganh
python ml/train_regime_model.py
```

Sau khi chạy xong, verify file mới tồn tại:
```bash
ls -la backend/src/main/resources/models/
# Phải thấy:
# stock_regime.onnx  (đã có)
# gold_trend.onnx    (MỚI)
```

### Acceptance Criteria:
- [ ] File `backend/src/main/resources/models/gold_trend.onnx` tồn tại
- [ ] Script train thành công, in F1-macro score
- [ ] Cả `stock_regime.onnx` và `gold_trend.onnx` cùng tồn tại

---

## TASK 7: Cập Nhật Frontend

### 7a. Sửa TypeScript types

**File**: `/mnt/d/Project_CT250H_NienLuanChuyenNganh/frontend/src/types/index.ts`

Tìm interface `RebalancePlan` (khoảng dòng 55-67):
```typescript
export interface RebalancePlan {
  driftDetected: boolean;
  maxDriftPercent: number;
  currentAllocations: Record<string, number>;
  targetAllocations: Record<string, number>;
  executiveSummary: string;
  actions: RebalanceAction[];
  totalEstimatedSell?: number;
  totalEstimatedBuy?: number;
  totalEstimatedFees?: number;
  totalEstimatedTax?: number;
  netCashImpact?: number;
}
```

**Sửa thành** (thêm 3 field mới + interface MlPrediction):
```typescript
export interface MlPredictionInfo {
  assetClass: string;
  modelName: string;
  signal: number;     // -1, 0, +1
  confidence: number; // 0.0 → 1.0
  regimeName: string;
  deltaWeight: number;
}

export interface RebalancePlan {
  driftDetected: boolean;
  maxDriftPercent: number;
  currentAllocations: Record<string, number>;
  targetAllocations: Record<string, number>;
  saaTargets?: Record<string, number>;
  taaTargets?: Record<string, number>;
  mlPredictions?: MlPredictionInfo[];
  executiveSummary: string;
  actions: RebalanceAction[];
  totalEstimatedSell?: number;
  totalEstimatedBuy?: number;
  totalEstimatedFees?: number;
  totalEstimatedTax?: number;
  netCashImpact?: number;
}
```

### 7b. Sửa `TaaTab.tsx` để hiển thị SAA vs TAA

**File**: `/mnt/d/Project_CT250H_NienLuanChuyenNganh/frontend/src/components/tabs/TaaTab.tsx`

Tìm đoạn đọc targets (khoảng dòng 32-36):
```typescript
  const currentStockTarget = ((plan?.targetAllocations?.STOCK ?? 0.40) * 100);
  const currentGoldTarget = ((plan?.targetAllocations?.GOLD ?? 0.20) * 100);
  const currentSavingsTarget = ((plan?.targetAllocations?.SAVINGS ?? 0.30) * 100);
  const currentCashTarget = ((plan?.targetAllocations?.CASH ?? 0.10) * 100);
```

**Thêm SAU đoạn đó:**
```typescript
  // SAA targets (mỏ neo gốc từ khảo sát)
  const saaStock = ((plan?.saaTargets?.STOCK ?? plan?.targetAllocations?.STOCK ?? 0.35) * 100);
  const saaGold = ((plan?.saaTargets?.GOLD ?? plan?.targetAllocations?.GOLD ?? 0.35) * 100);
  const saaSavings = ((plan?.saaTargets?.SAVINGS ?? plan?.targetAllocations?.SAVINGS ?? 0.20) * 100);
  const saaCash = ((plan?.saaTargets?.CASH ?? plan?.targetAllocations?.CASH ?? 0.10) * 100);

  // ML predictions
  const stockPrediction = plan?.mlPredictions?.find(p => p.assetClass === 'STOCK');
  const goldPrediction = plan?.mlPredictions?.find(p => p.assetClass === 'GOLD');
```

Tìm nơi hiển thị bảng tỷ trọng trong TaaTab (phần JSX) và **thêm một section mới** hiển thị ML info. Cụ thể, tìm nơi thích hợp trong JSX và thêm:

```tsx
{/* ML Regime Predictions */}
{plan?.mlPredictions && plan.mlPredictions.length > 0 && (
  <div style={{ marginTop: '24px', padding: '20px', background: '#f8fafc', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
    <h3 style={{ margin: '0 0 16px', fontSize: '16px', fontWeight: 600 }}>📡 Tín Hiệu Máy Học (ONNX T+20)</h3>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
      {plan.mlPredictions.map((ml) => (
        <div key={ml.assetClass} style={{
          padding: '16px', borderRadius: '10px', border: '1px solid #e2e8f0',
          background: ml.signal === 1 ? '#f0fdf4' : ml.signal === -1 ? '#fef2f2' : '#fffbeb'
        }}>
          <div style={{ fontWeight: 600, marginBottom: '8px' }}>
            {ml.assetClass === 'STOCK' ? '📈 Cổ phiếu VN30' : '🥇 Vàng SJC'}
          </div>
          <div style={{ fontSize: '14px', color: '#64748b' }}>
            <div>Tín hiệu: <strong style={{
              color: ml.signal === 1 ? '#16a34a' : ml.signal === -1 ? '#dc2626' : '#ca8a04'
            }}>
              {ml.signal === 1 ? '▲ Bullish (+1)' : ml.signal === -1 ? '▼ Bearish (-1)' : '◆ Sideway (0)'}
            </strong></div>
            <div>Độ tin cậy: <strong>{(ml.confidence * 100).toFixed(0)}%</strong></div>
            <div>Dịch chuyển: <strong>{ml.deltaWeight > 0 ? '+' : ''}{(ml.deltaWeight * 100).toFixed(1)}%</strong></div>
          </div>
        </div>
      ))}
    </div>

    {/* Bảng so sánh 3 cột */}
    <table style={{ width: '100%', marginTop: '16px', borderCollapse: 'collapse', fontSize: '14px' }}>
      <thead>
        <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
          <th style={{ textAlign: 'left', padding: '8px' }}>Lớp tài sản</th>
          <th style={{ textAlign: 'center', padding: '8px' }}>SAA (Mỏ neo)</th>
          <th style={{ textAlign: 'center', padding: '8px' }}>TAA (Sau ML)</th>
          <th style={{ textAlign: 'center', padding: '8px' }}>Thực tế</th>
        </tr>
      </thead>
      <tbody>
        {['STOCK', 'GOLD', 'SAVINGS', 'CASH'].map(cls => (
          <tr key={cls} style={{ borderBottom: '1px solid #f1f5f9' }}>
            <td style={{ padding: '8px', fontWeight: 500 }}>
              {cls === 'STOCK' ? '📈 Cổ phiếu' : cls === 'GOLD' ? '🥇 Vàng' : cls === 'SAVINGS' ? '🏦 Tiết kiệm' : '💵 Tiền mặt'}
            </td>
            <td style={{ textAlign: 'center', padding: '8px' }}>
              {((plan?.saaTargets?.[cls] ?? 0) * 100).toFixed(1)}%
            </td>
            <td style={{ textAlign: 'center', padding: '8px', fontWeight: 600,
              color: (plan?.taaTargets?.[cls] ?? 0) > (plan?.saaTargets?.[cls] ?? 0) ? '#16a34a' :
                     (plan?.taaTargets?.[cls] ?? 0) < (plan?.saaTargets?.[cls] ?? 0) ? '#dc2626' : '#0f172a'
            }}>
              {((plan?.taaTargets?.[cls] ?? 0) * 100).toFixed(1)}%
            </td>
            <td style={{ textAlign: 'center', padding: '8px' }}>
              {((plan?.currentAllocations?.[cls] ?? 0) * 100).toFixed(1)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
)}
```

### 7c. Sửa `OverviewTab.tsx` — đọc `taaTargets` thay vì `targetAllocations`

**File**: `/mnt/d/Project_CT250H_NienLuanChuyenNganh/frontend/src/components/tabs/OverviewTab.tsx`

Tìm dòng 219-222:
```typescript
  const targetStock = Math.round((plan?.targetAllocations.STOCK ?? 0.35) * 100);
  const targetGold = Math.round((plan?.targetAllocations.GOLD ?? 0.35) * 100);
  const targetSavings = Math.round((plan?.targetAllocations.SAVINGS ?? 0.20) * 100);
  const targetCash = Math.round((plan?.targetAllocations.CASH ?? 0.10) * 100);
```

**Sửa thành** (ưu tiên đọc `taaTargets`, fallback `targetAllocations`):
```typescript
  const targetStock = Math.round(((plan?.taaTargets?.STOCK ?? plan?.targetAllocations?.STOCK) ?? 0.35) * 100);
  const targetGold = Math.round(((plan?.taaTargets?.GOLD ?? plan?.targetAllocations?.GOLD) ?? 0.35) * 100);
  const targetSavings = Math.round(((plan?.taaTargets?.SAVINGS ?? plan?.targetAllocations?.SAVINGS) ?? 0.20) * 100);
  const targetCash = Math.round(((plan?.taaTargets?.CASH ?? plan?.targetAllocations?.CASH) ?? 0.10) * 100);
```

### Acceptance Criteria:
- [ ] `MlPredictionInfo` interface tồn tại trong `types/index.ts`
- [ ] `RebalancePlan` có fields `saaTargets`, `taaTargets`, `mlPredictions`
- [ ] `TaaTab` hiển thị bảng 3 cột SAA/TAA/Actual + badges ML regime
- [ ] `OverviewTab` đọc `taaTargets` thay vì `targetAllocations`

---

## Thứ Tự Thực Hiện

```
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7
  │         │         │         │         │         │         │
  │         │         │         │         │         │         └─ Frontend (độc lập)
  │         │         │         │         │         └─ ML training (độc lập, cần data)
  │         │         │         │         └─ SỬA OPTIMIZER (phụ thuộc 1,3,4)
  │         │         │         └─ Mở rộng DTO (độc lập)
  │         │         └─ Nâng cấp ONNX Service (phụ thuộc 1,2)
  │         └─ Feature Engineering (độc lập)
  └─ Record class (độc lập)
```

> [!WARNING]
> **Task 5 phải làm SAU task 1, 3, 4** vì nó import `RegimePrediction`, gọi method từ `OnnxRegimeService` mới, và dùng fields mới từ `RebalancePlanDTO`.

---

## Kiểm Tra Sau Khi Xong

1. **Build backend**: `cd backend && mvn compile` — phải KHÔNG có lỗi compile
2. **Chạy backend**: `mvn spring-boot:run` — check log:
   - `✅ Loaded ONNX Stock Regime model successfully.`
   - `✅ Loaded ONNX Gold Trend model successfully.` (hoặc warning nếu chưa train gold model)
3. **Test API**: `curl http://localhost:8080/api/v1/optimizer/rebalance-plan`
   - Response phải có fields: `saaTargets`, `taaTargets`, `mlPredictions`, `targetAllocations`
   - `targetAllocations` phải KHÁC `saaTargets` (nếu ML signal ≠ 0)
4. **Test Frontend**: Mở TaaTab, phải thấy bảng 3 cột SAA/TAA/Actual + badges ML regime
