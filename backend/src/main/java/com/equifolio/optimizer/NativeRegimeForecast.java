package com.equifolio.optimizer;

import java.util.List;

/** Decision scores; no component represents a calibrated confidence. */
public record NativeRegimeForecast(
    boolean available, String status, String session, String modelId,
    List<Double> classScores, Double netScore, boolean emaReset, String bundleSha256) {
  public static NativeRegimeForecast unavailable(String status) {
    return new NativeRegimeForecast(false, status, null, "shock_shrink_native", List.of(), null, false, null);
  }

  public int signal() {
    if (!available) return 0;
    int best = 0;
    for (int i = 1; i < 3; i++) if (classScores.get(i) > classScores.get(best)) best = i;
    return best - 1;
  }

  public String regimeName() {
    if (!available) return "UNAVAILABLE_" + status;
    return switch (signal()) {
      case -1 -> "NATIVE_BEARISH";
      case 1 -> "NATIVE_BULLISH";
      default -> "NATIVE_SIDEWAY";
    };
  }
}
