package com.equifolio.market;

import java.math.BigDecimal;
import java.time.*;

public record GoldObservation(String ticker, BigDecimal buy, BigDecimal sell, Instant observedAt) {
    public LocalDate date() { return observedAt.atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toLocalDate(); }
}
