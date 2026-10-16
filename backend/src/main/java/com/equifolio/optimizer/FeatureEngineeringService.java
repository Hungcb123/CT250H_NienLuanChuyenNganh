package com.equifolio.optimizer;

import com.equifolio.market.MarketPrice;
import com.equifolio.market.MarketPriceRepository;
import org.springframework.stereotype.Service;

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
