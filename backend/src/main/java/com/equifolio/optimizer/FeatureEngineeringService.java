package com.equifolio.optimizer;

import com.equifolio.market.MarketPrice;
import com.equifolio.market.MarketPriceRepository;
import org.springframework.stereotype.Service;

import java.util.List;

/** Computes the versioned close-only contract used by the exported ONNX models.
 * Formulas live in CloseFeatures and are checked against Python golden fixtures.
 */
@Service
public class FeatureEngineeringService {

    private final MarketPriceRepository marketPriceRepository;

    public FeatureEngineeringService(MarketPriceRepository marketPriceRepository) {
        this.marketPriceRepository = marketPriceRepository;
    }

    /**
     * Tính 12 close-v1 features cho một ticker từ market_prices trong DB.
     * Cần tối thiểu 60 phiên dữ liệu giá để tính đủ các chỉ báo.
     *
     * @param ticker Mã tài sản (VD: "VNINDEX" cho cổ phiếu, "GOLD_SJC" cho vàng)
     * @return float[12] features, hoặc null nếu không đủ dữ liệu
     */
    public float[] calculateFeatures(String ticker) {
        List<MarketPrice> prices = marketPriceRepository.findByAsset_TickerOrderByTradeDateAsc(ticker);
        if (prices == null || prices.size() < 60) return null;
        var last = prices.get(prices.size()-1).getTradeDate();
        var today = java.time.LocalDate.now(java.time.ZoneId.of("Asia/Ho_Chi_Minh"));
        if (last.isAfter(today) || last.isBefore(today.minusDays(7))) return null;
        try {
            return CloseFeatures.calculate(prices.stream().mapToDouble(p -> p.getPrice().doubleValue()).toArray());
        } catch (IllegalArgumentException ex) { return null; }
    }

}
