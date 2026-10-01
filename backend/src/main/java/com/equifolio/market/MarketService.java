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
}
