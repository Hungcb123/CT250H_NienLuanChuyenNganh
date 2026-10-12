package com.equifolio.market;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

public record MarketPriceDto(
        String ticker,
        String name,
        String assetClass,
        BigDecimal price,
        LocalDate tradeDate,
        Instant updatedAt,
        Double changeRatio,
        Double changeValue
) {
    public static MarketPriceDto from(MarketPrice mp) {
        String name = mp.getAsset() != null ? mp.getAsset().getName() : mp.getAsset().getTicker();
        String assetClass = mp.getAsset() != null ? mp.getAsset().getAssetClass() : "STOCK";
        return new MarketPriceDto(
                mp.getAsset().getTicker(),
                name,
                assetClass,
                mp.getPrice(),
                mp.getTradeDate(),
                mp.getUpdatedAt(),
                0.0,
                0.0
        );
    }

    public static MarketPriceDto from(MarketPrice mp, Double changeRatio, Double changeValue) {
        String name = mp.getAsset() != null ? mp.getAsset().getName() : mp.getAsset().getTicker();
        String assetClass = mp.getAsset() != null ? mp.getAsset().getAssetClass() : "STOCK";
        return new MarketPriceDto(
                mp.getAsset().getTicker(),
                name,
                assetClass,
                mp.getPrice(),
                mp.getTradeDate(),
                mp.getUpdatedAt(),
                changeRatio,
                changeValue
        );
    }
}
