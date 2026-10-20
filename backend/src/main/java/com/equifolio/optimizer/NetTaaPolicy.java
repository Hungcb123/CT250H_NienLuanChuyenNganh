package com.equifolio.optimizer;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** Bounded exposure preference from score difference; not expected return. */
public final class NetTaaPolicy {
  private NetTaaPolicy() {}

  public static BigDecimal weight(BigDecimal anchor, NativeRegimeForecast forecast,
                                 BigDecimal deltaMax, boolean enabled) {
    if (!enabled || forecast == null || !forecast.available() || forecast.netScore() == null) return anchor;
    double net = forecast.netScore();
    if (!Double.isFinite(net) || net < -1 || net > 1) return anchor;
    BigDecimal delta = deltaMax.multiply(BigDecimal.valueOf(net));
    return anchor.add(delta).max(BigDecimal.ZERO).min(BigDecimal.ONE)
        .setScale(4, RoundingMode.HALF_EVEN);
  }
}
