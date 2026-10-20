package com.equifolio.optimizer;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Arrays;
import org.junit.jupiter.api.Test;

class ModelContractTest {
  @Test
  void pythonJavaParityAndRealOnnxInference() throws Exception {
    var fixture =
        new ObjectMapper()
            .readTree(getClass().getResourceAsStream("/models/stock_regime_fixture.json"));
    double[] closes = new double[fixture.get("closes").size()];
    for (int i = 0; i < closes.length; i++) closes[i] = fixture.get("closes").get(i).asDouble();
    float[] features = CloseFeatures.calculate(closes);
    for (int i = 0; i < features.length; i++)
      assertEquals(fixture.get("features").get(i).asDouble(), features[i], 1e-4, "feature " + i);
    var engineering = mock(FeatureEngineeringService.class);
    when(engineering.calculateFeatures("VNINDEX")).thenReturn(features);
    var service = new OnnxRegimeService(engineering);
    service.init();
    try {
      var result = service.predictStockRegime();
      double probability = fixture.get("confidence").asDouble();
      if (probability >= .55) {
        assertEquals(fixture.get("label").asInt() - 1, result.signal());
        assertEquals(probability, result.confidence(), 1e-5);
        assertTrue(result.regimeName().startsWith("ONNX_"));
      } else {
        assertEquals(0, result.signal());
        assertEquals(0, result.confidence());
        assertTrue(result.regimeName().contains("LOW_CONFIDENCE"));
      }
      assertEquals(
          0, service.predictRegime(new float[14]), "Wrong shape must not become a heuristic trade");
      float[] invalid = features.clone();
      invalid[0] = Float.NaN;
      assertEquals(0, service.predictRegime(invalid));
      assertTrue(service.predictGoldRegime().regimeName().contains("ASSET_MISMATCH"));
      verify(engineering, never()).calculateFeatures("GOLD_SJC");
    } finally {
      service.cleanup();
    }
  }

  @Test
  void invalidAndFlatCloses() {
    double[] prices = new double[120];
    Arrays.fill(prices, 100);
    float[] flat = CloseFeatures.calculate(prices);
    assertEquals(50, flat[0]);
    assertEquals(0, flat[11]);
    prices[5] = 0;
    assertThrows(IllegalArgumentException.class, () -> CloseFeatures.calculate(prices));
  }

  @Test
  void optimizerFullyInvestedAndSensitiveToRisk() {
    double[] mu = {.1, .05};
    double[][] cov = {{.09, 0}, {0, .01}};
    double[] aggressive = HistoricalOptimizer.solve(mu, cov, 1),
        conservative = HistoricalOptimizer.solve(mu, cov, 10);
    assertEquals(1, Arrays.stream(aggressive).sum(), 1e-9);
    assertEquals(1, Arrays.stream(conservative).sum(), 1e-9);
    assertTrue(aggressive[0] > conservative[0]);
    for (double w : conservative) assertTrue(w >= 0 && w <= 1);
    // Analytic unconstrained interior solution: w_stock=(mu1-mu2+lambda*var2)/(lambda*(var1+var2)).
    assertEquals(.6, aggressive[0], 1e-7);
    assertEquals(.15, conservative[0], 1e-7);
  }
}
