package com.equifolio.market;

import com.equifolio.common.ApiResponse;
import org.springframework.web.bind.annotation.*;
import org.springframework.transaction.annotation.Transactional;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/api/v1/market")
public class GoldHistoryController {
    private final GoldPriceStore prices;
    public GoldHistoryController(GoldPriceStore prices) { this.prices = prices; }
    public record GoldBar(LocalDate date, BigDecimal close) {}
    @GetMapping("/gold-history")
    @Transactional(readOnly = true)
    public ApiResponse<List<GoldBar>> history(@RequestParam(defaultValue = "GOLD_SJC") String ticker) {
        if (!List.of("GOLD_SJC", "GOLD_RING_9999").contains(ticker)) {
            throw new IllegalArgumentException("Loại vàng không hợp lệ.");
        }
        return ApiResponse.success(prices.history(ticker).stream()
                .map(p -> new GoldBar(p.date(), p.close())).toList());
    }
}
