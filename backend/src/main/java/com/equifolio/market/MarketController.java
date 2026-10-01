package com.equifolio.market;

import com.equifolio.common.ApiResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/market")
public class MarketController {

    private final MarketService marketService;

    public MarketController(MarketService marketService) {
        this.marketService = marketService;
    }

    @GetMapping("/assets")
    public ResponseEntity<ApiResponse<List<Asset>>> getAssets() {
        return ResponseEntity.ok(ApiResponse.success(marketService.getAllAssets()));
    }

    @GetMapping("/prices")
    public ResponseEntity<ApiResponse<List<MarketPrice>>> getLatestPrices() {
        return ResponseEntity.ok(ApiResponse.success(marketService.getLatestMarketPrices()));
    }
}
