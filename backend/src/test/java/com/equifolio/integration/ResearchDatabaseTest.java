package com.equifolio.integration;

import static org.junit.jupiter.api.Assertions.*;

import com.equifolio.copilot.KnowledgeService;
import com.equifolio.goals.GoalService;
import com.equifolio.optimizer.HistoricalOptimizer;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.time.LocalDate;
import java.util.*;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.test.util.ReflectionTestUtils;

/** Opt-in, dedicated disposable PostgreSQL database; never points at the user's application DB. */
@EnabledIfEnvironmentVariable(named = "EQUIFOLIO_TEST_DB", matches = ".*equifolio_validation.*")
class ResearchDatabaseTest {
  @Test
  void migrationsPrivateKnowledgeGoalsAndHistoricalOptimization() throws Exception {
    var source =
        new DriverManagerDataSource(
            System.getenv("EQUIFOLIO_TEST_DB"),
            "postgres",
            System.getenv().getOrDefault("EQUIFOLIO_TEST_PASSWORD", "postgres"));
    Flyway.configure().dataSource(source).load().migrate();
    var jdbc = new JdbcTemplate(source);
    String suffix = UUID.randomUUID().toString().substring(0, 8);
    Long alice =
        jdbc.queryForObject(
            "INSERT INTO users(username,email,password_hash) VALUES(?,?,'test') RETURNING id",
            Long.class,
            "validation_alice_" + suffix,
            "validation_alice_" + suffix + "@example.test");
    Long bob =
        jdbc.queryForObject(
            "INSERT INTO users(username,email,password_hash) VALUES(?,?,'test') RETURNING id",
            Long.class,
            "validation_bob_" + suffix,
            "validation_bob_" + suffix + "@example.test");
    var knowledge = new KnowledgeService(jdbc, new ObjectMapper());
    assertEquals(
        1,
        knowledge.ingest(
            alice,
            new KnowledgeService.Document(
                "Cẩm nang nội bộ",
                "unit-test",
                "Lãi kép tích lũy đều đặn theo mục tiêu riêng zzzprivate")));
    assertFalse(knowledge.search(alice, "lãi kép").isEmpty(), "Vietnamese accents must match");
    assertTrue(
        knowledge.search(bob, "zzzprivate").isEmpty(),
        "Other users cannot retrieve private documents");
    assertEquals("FULL_TEXT", knowledge.search(alice, "zzzprivate").get(0).retrievalMode());
    // Exercise the actual pgvector RRF branch with a deterministic local embedding server.
    var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    List<Double> vector = new ArrayList<>(Collections.nCopies(1536, 0.));
    vector.set(0, 1.);
    byte[] payload =
        new ObjectMapper().writeValueAsBytes(Map.of("data", List.of(Map.of("embedding", vector))));
    server.createContext(
        "/embeddings",
        exchange -> {
          exchange.getRequestBody().readAllBytes();
          exchange.sendResponseHeaders(200, payload.length);
          exchange.getResponseBody().write(payload);
          exchange.close();
        });
    server.start();
    try {
      ReflectionTestUtils.setField(
          knowledge,
          "embeddingUrl",
          "http://127.0.0.1:" + server.getAddress().getPort() + "/embeddings");
      ReflectionTestUtils.setField(knowledge, "embeddingModel", "validation-vector");
      knowledge.ingest(
          alice,
          new KnowledgeService.Document(
              "Vector source", "vector-test", "zzzsemantic nguồn kiểm thử"));
      assertTrue(
          knowledge.search(alice, "zzzsemantic").stream()
              .anyMatch(s -> s.retrievalMode().equals("HYBRID_RRF")));
      assertTrue(knowledge.search(bob, "zzzsemantic").isEmpty());
    } finally {
      server.stop(0);
    }
    var goals = new GoalService(jdbc);
    var goal =
        new GoalService.GoalInput("Học phí", 1200, 0, 100, 0, LocalDate.now().plusYears(1), 0);
    Long id = goals.save(alice, null, goal);
    assertEquals(1, goals.list(alice).size());
    assertTrue(goals.list(bob).isEmpty());
    assertThrows(IllegalStateException.class, () -> goals.save(bob, id, goal));
    goals.save(alice, id, goal);
    assertThrows(IllegalStateException.class, () -> goals.save(alice, id, goal));
    goals.delete(alice, id);
    assertTrue(goals.list(alice).isEmpty());
    // Projection of real aligned observations, not hard-coded market parameters.
    var repository = org.mockito.Mockito.mock(com.equifolio.market.MarketPriceRepository.class);
    for (String ticker : List.of("FPT", "HPG")) {
      List<com.equifolio.market.MarketPrice> prices = new ArrayList<>();
      for (int i = 0; i < 90; i++)
        prices.add(
            new com.equifolio.market.MarketPrice(
                null,
                java.math.BigDecimal.valueOf(100 + i * (ticker.equals("FPT") ? 1 : .5)),
                LocalDate.now().minusDays(89 - i)));
      org.mockito.Mockito.when(repository.findByAsset_TickerOrderByTradeDateAsc(ticker))
          .thenReturn(prices);
    }
    var optimum = new HistoricalOptimizer(repository).optimize(List.of("FPT", "HPG"), 5);
    assertEquals(89, optimum.get("observations"));
    // An existing legacy snapshot remains auditable, and is never silently relabelled observed.
    jdbc.update(
        "INSERT INTO portfolio_snapshots(user_id,snapshot_date,total_nav) VALUES(?,?,?)",
        alice,
        LocalDate.now(),
        100);
    assertEquals(
        "LEGACY_UNVERIFIED",
        jdbc.queryForObject(
            "SELECT snapshot_source FROM portfolio_snapshots WHERE user_id=?",
            String.class,
            alice));
  }
}
