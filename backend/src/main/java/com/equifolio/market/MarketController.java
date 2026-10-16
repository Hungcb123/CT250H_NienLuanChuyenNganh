package com.equifolio.market;

import com.equifolio.common.ApiResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/market")
public class MarketController {

    private final MarketService marketService;
    private final ExternalMarketSyncService externalMarketSyncService;

    public MarketController(MarketService marketService, ExternalMarketSyncService externalMarketSyncService) {
        this.marketService = marketService;
        this.externalMarketSyncService = externalMarketSyncService;
    }

    @GetMapping("/gold-prices")
    public ResponseEntity<ApiResponse<List<GoldPriceDTO>>> getGoldPrices() {
        return ResponseEntity.ok(ApiResponse.success(externalMarketSyncService.getLatestGoldPrices()));
    }

    @GetMapping("/bank-rates")
    public ResponseEntity<ApiResponse<List<BankComparisonDTO>>> getBankRates() {
        return ResponseEntity.ok(ApiResponse.success(externalMarketSyncService.getBankComparison()));
    }

    @GetMapping("/risk-free-rate")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getRiskFreeRate() {
        return ResponseEntity.ok(ApiResponse.success(Map.of(
                "indicatorCode", "RF_INTERBANK_RATE",
                "indicatorName", "Lãi suất phi rủi ro (SBV Interbank Rate)",
                "rate", externalMarketSyncService.getRiskFreeRate(),
                "unit", "%"
        )));
    }

    @PostMapping("/sync-external")
    public ResponseEntity<ApiResponse<Map<String, Object>>> triggerExternalSync() {
        Map<String, Object> syncResult = externalMarketSyncService.syncAllExternal(true);
        return ResponseEntity.ok(ApiResponse.success("Đã đồng bộ giá Vàng và Biểu Lãi Suất Ngân Hàng thành công", syncResult));
    }

    @GetMapping("/assets")
    public ResponseEntity<ApiResponse<List<Asset>>> getAssets() {
        return ResponseEntity.ok(ApiResponse.success(marketService.getAllAssets()));
    }

    @GetMapping("/prices")
    public ResponseEntity<ApiResponse<List<MarketPriceDto>>> getLatestPrices() {
        return ResponseEntity.ok(ApiResponse.success(marketService.getLatestMarketPriceDtos()));
    }

    @GetMapping("/vnindex")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getVNIndex() {
        return ResponseEntity.ok(ApiResponse.success(marketService.getVNIndexSummary()));
    }

    @PostMapping("/sync")
    public ResponseEntity<ApiResponse<Map<String, Object>>> triggerSync() {
        return ResponseEntity.ok(ApiResponse.success("Đã đồng bộ dữ liệu thị trường từ DNSE OpenAPI thành công", marketService.syncMarketData()));
    }

    @GetMapping("/quote")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getQuote(@RequestParam String ticker) {
        Map<String, Object> quote = marketService.getLiveQuote(ticker);
        if (quote == null || quote.isEmpty()) {
            return ResponseEntity.badRequest().body(ApiResponse.error("Không tìm thấy dữ liệu khớp lệnh cho mã " + ticker.toUpperCase()));
        }
        return ResponseEntity.ok(ApiResponse.success(quote));
    }

    @PostMapping("/stocks")
    public ResponseEntity<ApiResponse<MarketPriceDto>> registerStock(
            @RequestParam String ticker,
            @RequestParam(required = false) String name,
            @RequestParam(required = false) String sector) {
        MarketPriceDto dto = marketService.registerOrFetchStock(ticker, name, sector);
        if (dto == null) {
            return ResponseEntity.badRequest().body(ApiResponse.error("Không thể đăng ký hoặc lấy giá cho mã " + ticker.toUpperCase()));
        }
        return ResponseEntity.ok(ApiResponse.success("Đã đồng bộ dữ liệu thị trường cho " + ticker.toUpperCase(), dto));
    }
}
