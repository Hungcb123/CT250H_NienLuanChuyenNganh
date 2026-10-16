package com.equifolio.market;

import java.math.BigDecimal;
import java.time.LocalDate;

public record GoldPriceDTO(
        String ticker,
        String name,
        BigDecimal buyPrice,
        BigDecimal sellPrice,
        Double changeValue,
        Double changePercent,
        String source,
        LocalDate tradeDate
) {}
