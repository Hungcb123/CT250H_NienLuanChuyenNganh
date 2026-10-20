package com.equifolio.optimizer;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.equifolio.ledger.*;
import com.equifolio.market.*;
import com.equifolio.profile.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import java.math.BigDecimal;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class NativeRegimeIntegrationTest {
  @Test
  void actualPythonWorkerRejectsStaleReviewedSnapshot() {
    String url = System.getProperty("regime.integration-url");
    org.junit.jupiter.api.Assumptions.assumeTrue(url != null);
    var result = new NativeRegimeService(url, "", new ObjectMapper()).predict();
    assertFalse(result.available());
    assertEquals("STALE_OR_INCOMPLETE_SESSION", result.status());
  }

  @Test
  void serverEndpointExposesNativeScoresWithoutProbabilityClaim() throws Exception {
    var service = mock(NativeRegimeService.class);
    when(service.predict()).thenReturn(forecast());
    var mvc = org.springframework.test.web.servlet.setup.MockMvcBuilders
        .standaloneSetup(new NativeRegimeController(service)).build();
    mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
        .post("/api/v1/research/native-regime/prediction"))
        .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isOk())
        .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.data.netScore").value(.06))
        .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.data.classScores[0]").value(.30));
  }
  private static NativeRegimeForecast forecast() {
    return new NativeRegimeForecast(true, "READY", LocalDate.now().toString(),
        "shock_shrink_native_snapshot_v1", List.of(.30, .34, .36), .06, false, "a".repeat(64));
  }

  @Test
  void netPolicyUsesScoreDifferenceAndBoundsInsteadOfWinningScore() {
    assertEquals(new BigDecimal("0.3590"), NetTaaPolicy.weight(new BigDecimal("0.35"), forecast(), new BigDecimal("0.15"), true));
    assertEquals(new BigDecimal("0.35"), NetTaaPolicy.weight(new BigDecimal("0.35"), forecast(), new BigDecimal("0.15"), false));
    assertEquals(new BigDecimal("0.35"), NetTaaPolicy.weight(new BigDecimal("0.35"), NativeRegimeForecast.unavailable("STALE_SESSION"), new BigDecimal("0.15"), true));
    var bear = new NativeRegimeForecast(true, "READY", "2026-10-01", "test", List.of(.7,.2,.1), -.6, false, "a");
    assertEquals(new BigDecimal("0.0000"), NetTaaPolicy.weight(new BigDecimal("0.02"), bear, new BigDecimal("0.15"), true));
  }

  @Test
  void realHttpClientAcceptsFullScoreContractAndRejectsMalformedOrUnavailable() throws Exception {
    var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    var sequence = new AtomicInteger();
    String today = LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh")).toString();
    String ready = """
      {"status":"READY","asset":"VNINDEX","mode":"live","session":"%s",
       "model_id":"shock_shrink_native_snapshot_v1","horizon_sessions":20,
       "class_scores":[0.30,0.34,0.36],"net_score":0.06,"signal":1,
       "score_semantics":"class_balanced_decision_scores_not_probabilities",
       "bundle_sha256":"%s","ema_reset":false}
      """.formatted(today, "a".repeat(64));
    server.createContext("/v1/predict", exchange -> {
      assertEquals("POST", exchange.getRequestMethod());
      assertEquals("Bearer test-token", exchange.getRequestHeaders().getFirst("Authorization"));
      int n = sequence.getAndIncrement();
      String body = switch(n) {
        case 0 -> ready;
        case 1 -> ready.replace("[0.30,0.34,0.36]", "[0.9,0.9,0.9]");
        case 2 -> ready.replace("\"live\"", "\"historical\"");
        default -> "{\"status\":\"STALE_OR_INCOMPLETE_SESSION\"}";
      };
      byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
      exchange.sendResponseHeaders(n < 3 ? 200 : 503, bytes.length);
      exchange.getResponseBody().write(bytes); exchange.close();
    });
    server.start();
    try {
      var client = new NativeRegimeService("http://127.0.0.1:"+server.getAddress().getPort(), "test-token", new ObjectMapper());
      var result = client.predict();
      assertTrue(result.available()); assertEquals(1,result.signal()); assertEquals(.06,result.netScore(),1e-12);
      assertEquals("INVALID_SCORES",client.predict().status());
      assertEquals("INVALID_CONTRACT",client.predict().status());
      assertEquals("STALE_OR_INCOMPLETE_SESSION",client.predict().status());
    } finally { server.stop(0); }
  }

  @Test
  void optimizerActuallyUsesNativeAndDoesNotFallbackToStockOnnx() {
    var ledger=mock(LedgerService.class);
    var targets=mock(PortfolioTargetRepository.class);
    var onnx=mock(OnnxRegimeService.class);
    var nativeModel=mock(NativeRegimeService.class);
    var optimizer=new PortfolioOptimizerService(ledger,targets,mock(MarketService.class),mock(AccountRepository.class),
        mock(TransactionRepository.class),mock(UserRepository.class),mock(AssetRepository.class),onnx,mock(SavingsDepositRepository.class));
    ReflectionTestUtils.setField(optimizer,"stockModel","native");
    ReflectionTestUtils.setField(optimizer,"nativeRegimeService",nativeModel);
    ReflectionTestUtils.setField(optimizer,"taaEnabled",true);
    var stock=new PortfolioTarget();stock.setAssetClass("STOCK");stock.setTargetWeight(new BigDecimal("0.35"));
    var gold=new PortfolioTarget();gold.setAssetClass("GOLD");gold.setTargetWeight(new BigDecimal("0.35"));
    when(targets.findByUserId(1L)).thenReturn(List.of(stock,gold));
    when(ledger.calculatePortfolioValuation(1L)).thenReturn(new PortfolioValuationDTO());
    when(onnx.predictGoldRegime()).thenReturn(new RegimePrediction(0,0,"UNAVAILABLE_GOLD"));
    when(nativeModel.predict()).thenReturn(forecast());
    var plan=optimizer.generateRebalancePlan(1L);
    assertEquals(new BigDecimal("0.3590"),plan.getTaaTargets().get("STOCK"));
    assertEquals(.06,plan.getMlPredictions().get(0).getNativeForecast().netScore(),1e-12);
    assertEquals(0,plan.getMlPredictions().get(0).getConfidence());
    verify(onnx,never()).predictStockRegime();
    when(nativeModel.predict()).thenReturn(NativeRegimeForecast.unavailable("STALE_SESSION"));
    assertEquals(new BigDecimal("0.35"),optimizer.generateRebalancePlan(1L).getTaaTargets().get("STOCK"));
  }
}
