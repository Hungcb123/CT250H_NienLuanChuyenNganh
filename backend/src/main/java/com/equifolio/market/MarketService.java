package com.equifolio.market;

import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;

@Service
public class MarketService {

    private final AssetRepository assetRepository;
    private final MarketPriceRepository marketPriceRepository;

    public MarketService(AssetRepository assetRepository, MarketPriceRepository marketPriceRepository) {
        this.assetRepository = assetRepository;
        this.marketPriceRepository = marketPriceRepository;
    }

    public List<Asset> getAllAssets() {
        return assetRepository.findAll();
    }

    public List<MarketPrice> getLatestMarketPrices() {
        return marketPriceRepository.findAllLatestPrices();
    }

    public BigDecimal getLatestPrice(String ticker) {
        if ("VND".equalsIgnoreCase(ticker) || "EQUITY".equalsIgnoreCase(ticker)) {
            return BigDecimal.ONE;
        }
        return marketPriceRepository.findLatestPriceByTicker(ticker)
                .map(MarketPrice::getPrice)
                .orElse(BigDecimal.ZERO);
    }

    public java.util.Map<String, Object> getVNIndexSummary() {
        java.util.Map<String, Object> summary = new java.util.HashMap<>();
        summary.put("latestDate", "2026-10-01");
        summary.put("currentPoints", 1749.30);
        summary.put("changePoints", -19.32);
        summary.put("changePercent", -1.09);
        summary.put("high52w", 1933.11);
        summary.put("low52w", 1578.42);
        summary.put("latestVolume", 449376366L);
        summary.put("avgVolume20", 507233239L);
        summary.put("ma20", 1802.97);
        summary.put("ma50", 1772.95);
        summary.put("regimeSignal", 1);
        summary.put("regimeStatus", "BULLISH_CONSOLIDATION");
        return summary;
    }
}
