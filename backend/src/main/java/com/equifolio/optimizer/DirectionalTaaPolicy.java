package com.equifolio.optimizer;
import java.math.BigDecimal;

public final class DirectionalTaaPolicy {
    private DirectionalTaaPolicy() {}
    public static BigDecimal weight(BigDecimal anchor, NativeRegimeForecast forecast, boolean enabled) {
        if (!enabled || forecast == null || !forecast.available()) return anchor;
        return weight(anchor, forecast.signal(), true);
    }
    public static BigDecimal weight(BigDecimal anchor, int signal, boolean enabled) {
        if (!enabled || signal < -1 || signal > 1) return anchor;
        return anchor.add(new BigDecimal("0.10").multiply(BigDecimal.valueOf(signal)))
            .max(BigDecimal.ZERO).min(BigDecimal.ONE);
    }
}
