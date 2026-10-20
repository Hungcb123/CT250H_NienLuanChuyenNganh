package com.equifolio.optimizer;

import java.util.Arrays;

/** Exact close-v1 contract shared with ml/regime_pipeline.py. */
public final class CloseFeatures {
  public static final String VERSION = "close-v1";
  public static final String NAMES =
      "RSI_14,MACD,MACD_Signal,MACD_Hist,BB_Width,BB_PctB,SMA_20_50_Ratio,Dist_SMA20,Dist_SMA50,Abs_Change_14_Pct,ROC_20,HV_20";

  private CloseFeatures() {}

  public static float[] calculate(double[] values) {
    if (values.length < 60) throw new IllegalArgumentException("Cần ít nhất 60 phiên giá");
    double[] p = Arrays.copyOfRange(values, Math.max(0, values.length - 120), values.length);
    for (double x : p)
      if (!Double.isFinite(x) || x <= 0) throw new IllegalArgumentException("Giá không hợp lệ");
    int n = p.length;
    double gain = 0, loss = 0, abs = 0;
    for (int i = n - 14; i < n; i++) {
      double d = p[i] - p[i - 1];
      gain += Math.max(0, d);
      loss += Math.max(0, -d);
      abs += Math.abs(d);
    }
    double rsi = gain == 0 && loss == 0 ? 50 : loss == 0 ? 100 : 100 - 100 / (1 + gain / loss);
    double[] fast = ema(p, 12), slow = ema(p, 26), macd = new double[n];
    for (int i = 0; i < n; i++) macd[i] = (fast[i] - slow[i]) / p[i] * 100;
    double signal = ema(macd, 9)[n - 1], s20 = mean(p, n - 20, n), s50 = mean(p, n - 50, n), v = 0;
    for (int i = n - 20; i < n; i++) v += Math.pow(p[i] - s20, 2);
    double std = Math.sqrt(v / 20), last = p[n - 1];
    double[] lr = new double[20];
    for (int i = 0; i < 20; i++) lr[i] = Math.log(p[n - 20 + i] / p[n - 21 + i]);
    double m = mean(lr, 0, 20), lv = 0;
    for (double r : lr) lv += Math.pow(r - m, 2);
    return new float[] {
      (float) rsi,
      (float) macd[n - 1],
      (float) signal,
      (float) (macd[n - 1] - signal),
      (float) (4 * std / s20),
      (float) (std == 0 ? .5 : (last - s20 + 2 * std) / (4 * std)),
      (float) (s20 / s50),
      (float) (last / s20 - 1),
      (float) (last / s50 - 1),
      (float) (abs / 14 / last * 100),
      (float) ((last / p[n - 21] - 1) * 100),
      (float) (Math.sqrt(lv / 19) * Math.sqrt(252) * 100)
    };
  }

  private static double mean(double[] p, int a, int b) {
    double s = 0;
    for (int i = a; i < b; i++) s += p[i];
    return s / (b - a);
  }

  private static double[] ema(double[] p, int period) {
    double[] r = new double[p.length];
    r[0] = p[0];
    for (int i = 1; i < p.length; i++) r[i] = r[i - 1] + (p[i] - r[i - 1]) * 2 / (period + 1);
    return r;
  }
}
