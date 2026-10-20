package com.equifolio.market;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class MarketService {

    private final AssetRepository assetRepository;
    private final MarketPriceRepository marketPriceRepository;
    private final DnseMarketDataService dnseMarketDataService;

    public MarketService(AssetRepository assetRepository,
                         MarketPriceRepository marketPriceRepository,
                         DnseMarketDataService dnseMarketDataService) {
        this.assetRepository = assetRepository;
        this.marketPriceRepository = marketPriceRepository;
        this.dnseMarketDataService = dnseMarketDataService;
    }

    public List<Asset> getAllAssets() {
        return assetRepository.findAll();
    }

    public List<MarketPrice> getLatestMarketPrices() {
        return marketPriceRepository.findAllLatestPrices();
    }

    public List<MarketPriceDto> getLatestMarketPriceDtos() {
        List<MarketPrice> latest = marketPriceRepository.findAllLatestPrices();
        List<MarketPriceDto> dtos = new ArrayList<>();

        for (MarketPrice mp : latest) {
            String ticker = mp.getAsset().getTicker();
            Double changeRatio = 0.0;
            Double changeValue = 0.0;

            // Fetch the last 2 prices to compute day-over-day change
            List<MarketPrice> history = marketPriceRepository.findByAsset_TickerOrderByTradeDateAsc(ticker);
            if (history.size() >= 2) {
                BigDecimal current = history.get(history.size() - 1).getPrice();
                BigDecimal prev = history.get(history.size() - 2).getPrice();
                if (prev.compareTo(BigDecimal.ZERO) > 0) {
                    BigDecimal diff = current.subtract(prev);
                    changeValue = diff.doubleValue();
                    changeRatio = diff.doubleValue() / prev.doubleValue() * 100.0;
                    changeRatio = Math.round(changeRatio * 100.0) / 100.0;
                }
            }

            dtos.add(MarketPriceDto.from(mp, changeRatio, changeValue));
        }

        return dtos;
    }

    public BigDecimal getLatestPrice(String ticker) {
        if ("VND".equalsIgnoreCase(ticker) || "EQUITY".equalsIgnoreCase(ticker)) {
            return BigDecimal.ONE;
        }
        return marketPriceRepository.findLatestPriceByTicker(ticker)
                .map(MarketPrice::getPrice)
                .orElse(BigDecimal.ZERO);
    }

    public void saveOrUpdatePrice(Asset asset, BigDecimal price) {
        if (price == null || price.compareTo(BigDecimal.ZERO) <= 0) return;
        java.time.LocalDate today = java.time.LocalDate.now();
        MarketPrice mp = marketPriceRepository.findLatestPriceByTicker(asset.getTicker())
                .filter(p -> p.getTradeDate().equals(today))
                .orElse(new MarketPrice(asset, price, today));
        mp.setPrice(price);
        marketPriceRepository.save(mp);
    }

    public Map<String, Object> getVNIndexSummary() {
        Map<String, Object> summary = dnseMarketDataService.getVNIndexSummary();
        if (summary != null && !summary.isEmpty()) {
            return summary;
        }

        throw new IllegalStateException("Chưa tải được dữ liệu VNINDEX từ DNSE. Vui lòng thử đồng bộ lại.");
    }

    public Map<String, Object> syncMarketData() {
        return dnseMarketDataService.syncAll();
    }

    public Map<String, Object> getLiveQuote(String ticker) {
        return dnseMarketDataService.fetchLiveQuote(ticker);
    }

    @Transactional
    public MarketPriceDto registerOrFetchStock(String ticker, String name, String sector) {
        if (ticker == null || ticker.isBlank()) {
            return null;
        }
        String cleanTicker = ticker.trim().toUpperCase();
        Asset asset = assetRepository.findById(cleanTicker).orElseGet(() -> {
            Asset newAsset = new Asset();
            newAsset.setTicker(cleanTicker);
            newAsset.setName(name != null && !name.isBlank() ? name.trim() : "CTCP " + cleanTicker);
            newAsset.setAssetClass("STOCK");
            return assetRepository.save(newAsset);
        });

        // Immediately backfill candles for this asset from DNSE
        LocalDate today = LocalDate.now(ZoneId.of("Asia/Bangkok"));
        dnseMarketDataService.backfillStock(asset, today);

        return marketPriceRepository.findLatestPriceByTicker(cleanTicker)
                .map(mp -> {
                    Double changeRatio = 0.0;
                    Double changeValue = 0.0;
                    List<MarketPrice> history = marketPriceRepository.findByAsset_TickerOrderByTradeDateAsc(cleanTicker);
                    if (history.size() >= 2) {
                        BigDecimal current = history.get(history.size() - 1).getPrice();
                        BigDecimal prev = history.get(history.size() - 2).getPrice();
                        if (prev.compareTo(BigDecimal.ZERO) > 0) {
                            BigDecimal diff = current.subtract(prev);
                            changeValue = diff.doubleValue();
                            changeRatio = Math.round(diff.doubleValue() / prev.doubleValue() * 10000.0) / 100.0;
                        }
                    }
                    return MarketPriceDto.from(mp, changeRatio, changeValue);
                })
                .orElse(null);
    }
}
