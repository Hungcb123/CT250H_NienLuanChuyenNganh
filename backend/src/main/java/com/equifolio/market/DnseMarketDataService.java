package com.equifolio.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Background Service for ingesting and backfilling real-time/historical
 * market data from DNSE OpenAPI & Market Data Feeds.
 */
@Service
public class DnseMarketDataService {

    private static final Logger log = LoggerFactory.getLogger(DnseMarketDataService.class);
    private static final ZoneId VN_ZONE = ZoneId.of("Asia/Bangkok");
    private static final String DNSE_CHART_API_BASE = "https://services.entrade.com.vn/chart-api/v2";

    private final AssetRepository assetRepository;
    private final MarketPriceRepository marketPriceRepository;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;

    // Cache for VNINDEX summary calculated from DNSE index candles
    private final Map<String, Object> vnIndexSummaryCache = new ConcurrentHashMap<>();

    public DnseMarketDataService(AssetRepository assetRepository,
                                 MarketPriceRepository marketPriceRepository,
                                 ObjectMapper objectMapper) {
        this.assetRepository = assetRepository;
        this.marketPriceRepository = marketPriceRepository;
        this.objectMapper = objectMapper;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(6))
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
    }

    /**
     * Initial background sync on application startup.
     */
    @Async
    @EventListener(ApplicationReadyEvent.class)
    public void onApplicationReady() {
        log.info("[DNSE Market Data] Server started. Triggering initial background backfill...");
        try {
            // Small pause to allow database migrations and pool initialization
            Thread.sleep(2000);
            syncAll();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (Exception e) {
            log.error("[DNSE Market Data] Error during initial startup backfill: {}", e.getMessage(), e);
        }
    }

    /**
     * Periodic background sync: runs every 15 minutes during VN stock trading hours (09:00 - 15:30, Mon-Fri).
     */
    @Scheduled(cron = "0 */15 9-16 * * MON-FRI", zone = "Asia/Bangkok")
    public void scheduledTradingHoursSync() {
        log.info("[DNSE Market Data] Scheduled trading-hour background market data sync initiated.");
        syncAll();
    }

    /**
     * Fallback periodic sync: runs every hour to catch up any missed daily bars.
     */
    @Scheduled(fixedDelay = 3600000, initialDelay = 1800000)
    public void scheduledHourlyCatchup() {
        log.info("[DNSE Market Data] Periodic hourly background check initiated.");
        syncAll();
    }

    /**
     * Synchronize all tracked assets and VN-Index.
     */
    @Transactional
    public Map<String, Object> syncAll() {
        LocalDate today = LocalDate.now(VN_ZONE);
        log.info("[DNSE Market Data] Syncing market data up to date: {}", today);

        List<Asset> assets = assetRepository.findAll();
        Map<String, Object> syncReport = new LinkedHashMap<>();
        int totalSavedOrUpdated = 0;
        List<String> syncedTickers = new ArrayList<>();

        // 1. Sync Stock Assets from DNSE Chart API
        for (Asset asset : assets) {
            if ("STOCK".equalsIgnoreCase(asset.getAssetClass())) {
                try {
                    int count = backfillStock(asset, today);
                    totalSavedOrUpdated += count;
                    syncedTickers.add(asset.getTicker() + " (" + count + " bars)");
                } catch (Exception e) {
                    log.error("[DNSE Market Data] Failed to sync stock {}: {}", asset.getTicker(), e.getMessage());
                }
            } else if ("GOLD".equalsIgnoreCase(asset.getAssetClass())) {
                // Ensure Gold has latest entry for today if trading date missing
                carryForwardLatestPrice(asset, today);
            } else if ("CASH".equalsIgnoreCase(asset.getAssetClass()) && "VND".equalsIgnoreCase(asset.getTicker())) {
                ensureVndPrice(asset, today);
            }
        }

        // 2. Sync VN-Index summary
        try {
            syncVNIndex();
            syncReport.put("vnindex", vnIndexSummaryCache);
        } catch (Exception e) {
            log.error("[DNSE Market Data] Failed to sync VN-Index: {}", e.getMessage());
        }

        syncReport.put("syncedAt", Instant.now().toString());
        syncReport.put("targetDate", today.toString());
        syncReport.put("syncedTickers", syncedTickers);
        syncReport.put("totalRecordsUpdated", totalSavedOrUpdated);
        log.info("[DNSE Market Data] Sync completed: {} records updated. Tickers: {}", totalSavedOrUpdated, syncedTickers);

        return syncReport;
    }

    /**
     * Backfill missing historical daily candles for a stock ticker up to today.
     */
    public int backfillStock(Asset asset, LocalDate today) {
        String ticker = asset.getTicker();
        Optional<LocalDate> maxDateOpt = marketPriceRepository.findMaxTradeDateByTicker(ticker);

        // Determine fromDate: if never synced or outdated, fetch past 30 days
        LocalDate fromDate = maxDateOpt.orElse(today.minusDays(30));
        // Backtrack 3 days to verify any adjustments or previous closes
        fromDate = fromDate.minusDays(3);

        long fromTs = fromDate.atStartOfDay(VN_ZONE).toEpochSecond();
        long toTs = Instant.now().getEpochSecond() + 86400; // include current day

        String url = String.format("%s/ohlcs/stock?symbol=%s&from=%d&to=%d&resolution=1D",
                DNSE_CHART_API_BASE, ticker, fromTs, toTs);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .timeout(Duration.ofSeconds(6))
                .header("User-Agent", "Mozilla/5.0 EquiFolio/1.0")
                .header("Accept", "application/json")
                .GET()
                .build();

        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                log.warn("[DNSE Market Data] Stock {} returned HTTP {}", ticker, response.statusCode());
                return 0;
            }

            JsonNode root = objectMapper.readTree(response.body());
            JsonNode times = root.get("t");
            JsonNode closes = root.get("c");

            if (times == null || closes == null || !times.isArray() || times.isEmpty()) {
                log.warn("[DNSE Market Data] No candle data for stock {}", ticker);
                return 0;
            }

            int count = 0;
            for (int i = 0; i < times.size(); i++) {
                long epochSec = times.get(i).asLong();
                double closeThousand = closes.get(i).asDouble();
                if (closeThousand <= 0) continue;

                // DNSE quote prices are in thousand VND (e.g. 20.15 = 20,150 VND)
                BigDecimal priceVnd = BigDecimal.valueOf(closeThousand * 1000.0);
                LocalDate tradeDate = Instant.ofEpochSecond(epochSec).atZone(VN_ZONE).toLocalDate();

                Optional<MarketPrice> existing = marketPriceRepository.findByAsset_TickerAndTradeDate(ticker, tradeDate);
                if (existing.isPresent()) {
                    MarketPrice mp = existing.get();
                    mp.setPrice(priceVnd);
                    mp.setUpdatedAt(Instant.now());
                    marketPriceRepository.save(mp);
                } else {
                    MarketPrice mp = new MarketPrice(asset, priceVnd, tradeDate);
                    marketPriceRepository.save(mp);
                }
                count++;
            }

            log.info("[DNSE Market Data] {} backfilled {} daily bars up to {}", ticker, count, today);
            return count;
        } catch (Exception e) {
            log.error("[DNSE Market Data] Error fetching stock {}: {}", ticker, e.getMessage());
            return 0;
        }
    }

    /**
     * Carry forward the latest known gold price to today if today has no record.
     */
    private void carryForwardLatestPrice(Asset asset, LocalDate today) {
        Optional<MarketPrice> todayPrice = marketPriceRepository.findByAsset_TickerAndTradeDate(asset.getTicker(), today);
        if (todayPrice.isEmpty()) {
            marketPriceRepository.findLatestPriceByTicker(asset.getTicker()).ifPresent(latest -> {
                MarketPrice mp = new MarketPrice(asset, latest.getPrice(), today);
                marketPriceRepository.save(mp);
                log.info("[DNSE Market Data] Gold {} carried forward price {} for {}", asset.getTicker(), latest.getPrice(), today);
            });
        }
    }

    /**
     * Ensure VND cash asset has price 1.0 for today.
     */
    private void ensureVndPrice(Asset asset, LocalDate today) {
        Optional<MarketPrice> todayPrice = marketPriceRepository.findByAsset_TickerAndTradeDate(asset.getTicker(), today);
        if (todayPrice.isEmpty()) {
            MarketPrice mp = new MarketPrice(asset, BigDecimal.ONE, today);
            marketPriceRepository.save(mp);
        }
    }

    /**
     * Synchronize VN-Index historical daily series and calculate real-time technical indicators.
     */
    private void syncVNIndex() {
        long now = Instant.now().getEpochSecond();
        long fromTs = now - (400L * 86400L); // fetch ~400 days for 52-week & MA50 metrics

        String url = String.format("%s/ohlcs/index?symbol=VNINDEX&from=%d&to=%d&resolution=1D",
                DNSE_CHART_API_BASE, fromTs, now);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .timeout(Duration.ofSeconds(6))
                .header("User-Agent", "Mozilla/5.0 EquiFolio/1.0")
                .header("Accept", "application/json")
                .GET()
                .build();

        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                log.warn("[DNSE Market Data] VNINDEX returned HTTP {}", response.statusCode());
                return;
            }

            JsonNode root = objectMapper.readTree(response.body());
            JsonNode times = root.get("t");
            JsonNode closes = root.get("c");
            JsonNode volumes = root.get("v");

            if (times == null || closes == null || times.isEmpty()) {
                return;
            }

            int n = closes.size();
            List<Double> closeList = new ArrayList<>(n);
            List<Long> volList = new ArrayList<>(n);
            List<LocalDate> dateList = new ArrayList<>(n);

            for (int i = 0; i < n; i++) {
                closeList.add(closes.get(i).asDouble());
                volList.add(volumes != null && i < volumes.size() ? volumes.get(i).asLong() : 0L);
                dateList.add(Instant.ofEpochSecond(times.get(i).asLong()).atZone(VN_ZONE).toLocalDate());
            }

            double latestClose = closeList.get(n - 1);
            double prevClose = n >= 2 ? closeList.get(n - 2) : latestClose;
            double changePoints = Math.round((latestClose - prevClose) * 100.0) / 100.0;
            double changePercent = Math.round((changePoints / prevClose * 100.0) * 100.0) / 100.0;
            LocalDate latestDate = dateList.get(n - 1);
            long latestVolume = volList.get(n - 1);

            // 52-week High / Low
            int barsFor52w = Math.min(n, 252);
            double high52w = closeList.subList(n - barsFor52w, n).stream().max(Double::compare).orElse(latestClose);
            double low52w = closeList.subList(n - barsFor52w, n).stream().min(Double::compare).orElse(latestClose);

            // Moving Averages
            int ma20Bars = Math.min(n, 20);
            double ma20 = closeList.subList(n - ma20Bars, n).stream().mapToDouble(Double::doubleValue).average().orElse(latestClose);
            ma20 = Math.round(ma20 * 100.0) / 100.0;

            int ma50Bars = Math.min(n, 50);
            double ma50 = closeList.subList(n - ma50Bars, n).stream().mapToDouble(Double::doubleValue).average().orElse(latestClose);
            ma50 = Math.round(ma50 * 100.0) / 100.0;

            // Average Volume 20
            long avgVol20 = (long) volList.subList(n - ma20Bars, n).stream().mapToLong(Long::longValue).average().orElse(latestVolume);

            // Regime classification
            int regimeSignal = latestClose >= ma20 ? 1 : 0;
            String regimeStatus = latestClose >= ma20 ? "BULLISH_CONSOLIDATION" : "DEFENSIVE_CORRECTION";

            vnIndexSummaryCache.put("latestDate", latestDate.toString());
            vnIndexSummaryCache.put("currentPoints", Math.round(latestClose * 100.0) / 100.0);
            vnIndexSummaryCache.put("changePoints", changePoints);
            vnIndexSummaryCache.put("changePercent", changePercent);
            vnIndexSummaryCache.put("high52w", Math.round(high52w * 100.0) / 100.0);
            vnIndexSummaryCache.put("low52w", Math.round(low52w * 100.0) / 100.0);
            vnIndexSummaryCache.put("latestVolume", latestVolume);
            vnIndexSummaryCache.put("avgVolume20", avgVol20);
            vnIndexSummaryCache.put("ma20", ma20);
            vnIndexSummaryCache.put("ma50", ma50);
            vnIndexSummaryCache.put("regimeSignal", regimeSignal);
            vnIndexSummaryCache.put("regimeStatus", regimeStatus);
            vnIndexSummaryCache.put("source", "DNSE_OPENAPI_KRX");

            log.info("[DNSE Market Data] VN-Index updated: {} pts ({}{}%), MA20={}, MA50={}, Date={}",
                    latestClose, changePoints >= 0 ? "+" : "", changePoints, ma20, ma50, latestDate);
        } catch (Exception e) {
            log.error("[DNSE Market Data] Failed to calculate VN-Index summary: {}", e.getMessage());
        }
    }

    /**
     * Get the live or cached VN-Index technical summary.
     */
    public Map<String, Object> getVNIndexSummary() {
        if (vnIndexSummaryCache.isEmpty()) {
            syncVNIndex();
        }
        return new LinkedHashMap<>(vnIndexSummaryCache);
    }

    /**
     * Fetch on-demand live quote for any stock ticker from DNSE OpenAPI.
     */
    public Map<String, Object> fetchLiveQuote(String ticker) {
        if (ticker == null || ticker.isBlank()) {
            return Collections.emptyMap();
        }
        String cleanTicker = ticker.trim().toUpperCase();
        long now = Instant.now().getEpochSecond();
        long fromTs = now - (10 * 86400); // 10 days window to capture today & previous session
        long toTs = now + 86400;

        String url = String.format("%s/ohlcs/stock?symbol=%s&from=%d&to=%d&resolution=1D",
                DNSE_CHART_API_BASE, cleanTicker, fromTs, toTs);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .timeout(Duration.ofSeconds(6))
                .header("User-Agent", "Mozilla/5.0 EquiFolio/1.0")
                .header("Accept", "application/json")
                .GET()
                .build();

        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                log.warn("[DNSE Quote] Ticker {} returned HTTP {}", cleanTicker, response.statusCode());
                return Collections.emptyMap();
            }

            JsonNode root = objectMapper.readTree(response.body());
            JsonNode closes = root.get("c");
            JsonNode volumes = root.get("v");
            JsonNode times = root.get("t");

            if (closes == null || !closes.isArray() || closes.isEmpty()) {
                return Collections.emptyMap();
            }

            int size = closes.size();
            double latestClose = closes.get(size - 1).asDouble() * 1000.0;
            double prevClose = size >= 2 ? closes.get(size - 2).asDouble() * 1000.0 : latestClose;
            long latestVolume = volumes != null && volumes.size() >= size ? volumes.get(size - 1).asLong() : 0L;
            long tradeDateTs = times != null && times.size() >= size ? times.get(size - 1).asLong() : now;

            double change = latestClose - prevClose;
            double changePercent = prevClose > 0 ? (change / prevClose * 100.0) : 0.0;
            changePercent = Math.round(changePercent * 100.0) / 100.0;

            Map<String, Object> quote = new LinkedHashMap<>();
            quote.put("ticker", cleanTicker);
            quote.put("price", latestClose);
            quote.put("prevPrice", prevClose);
            quote.put("change", Math.round(change));
            quote.put("changePercent", changePercent);
            quote.put("volume", latestVolume);
            quote.put("tradeDate", Instant.ofEpochSecond(tradeDateTs).atZone(VN_ZONE).toLocalDate().toString());
            quote.put("source", "DNSE_OPENAPI_KRX");
            return quote;
        } catch (Exception e) {
            log.error("[DNSE Quote] Failed to fetch quote for {}: {}", cleanTicker, e.getMessage());
            return Collections.emptyMap();
        }
    }
}
