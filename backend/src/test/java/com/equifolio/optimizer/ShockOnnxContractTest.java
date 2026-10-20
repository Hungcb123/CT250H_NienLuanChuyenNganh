package com.equifolio.optimizer;

import static org.junit.jupiter.api.Assertions.*;

import ai.onnxruntime.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.DoubleBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** Runs the complete frozen Python ensemble in the project's Java ONNX Runtime. */
class ShockOnnxContractTest {
  @Test
  void fullEnsembleMatchesPythonForColdAndCarriedEma() throws Exception {
    var packaged = Path.of(getClass().getResource("/models/shock/checksums.json").toURI()).getParent();
    var directory = Path.of(System.getProperty("shock.onnx.dir", packaged.toString()));
    var mapper = new ObjectMapper();
    var checksums = mapper.readTree(directory.resolve("checksums.json").toFile());
    for (var entries = checksums.fields(); entries.hasNext(); ) {
      var entry = entries.next();
      var hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
          .digest(Files.readAllBytes(directory.resolve(entry.getKey()))));
      assertEquals(entry.getValue().asText(), hash, entry.getKey());
    }
    var contract = mapper.readTree(directory.resolve("contract.json").toFile());
    assertFalse(contract.get("class_scores_are_probabilities").asBoolean());
    var fixtures = mapper.readTree(directory.resolve("parity_fixture.json").toFile());
    assertEquals(2, fixtures.size());
    var environment = OrtEnvironment.getEnvironment();
    try (var options = new OrtSession.SessionOptions()) {
      options.setIntraOpNumThreads(2);
      options.setInterOpNumThreads(1);
      try (var session = environment.createSession(
          directory.resolve("shock_regime.onnx").toString(), options)) {
        for (var fixture : fixtures) {
          try (var features = OnnxTensor.createTensor(environment, matrix(fixture.get("features")));
              var sigma = OnnxTensor.createTensor(environment,
                  DoubleBuffer.wrap(vector(fixture.get("horizon_sigma"))), new long[] {1});
              var parameters = OnnxTensor.createTensor(environment,
                  DoubleBuffer.wrap(vector(fixture.get("parameters"))), new long[] {3});
              var previous = OnnxTensor.createTensor(environment, matrix(fixture.get("previous_ema")));
              var contiguous = OnnxTensor.createTensor(environment, fixture.get("contiguous").asBoolean());
              var result = session.run(Map.of("features", features, "horizon_sigma", sigma,
                  "parameters", parameters, "previous_ema", previous, "contiguous", contiguous))) {
            assertArrayEquals(vector(fixture.get("class_scores").get(0)),
                ((double[][]) result.get("class_scores").orElseThrow().getValue())[0], 1e-5);
            assertEquals(fixture.get("signal").get(0).asLong(),
                ((long[]) result.get("signal").orElseThrow().getValue())[0]);
            for (var entries = fixture.get("components").fields(); entries.hasNext(); ) {
              var entry = entries.next();
              assertArrayEquals(vector(entry.getValue().get(0)),
                  ((double[][]) result.get(entry.getKey()).orElseThrow().getValue())[0],
                  1e-5, entry.getKey());
            }
          }
        }
      }
    }
  }

  private static double[] vector(JsonNode node) {
    var values = new double[node.size()];
    for (int i = 0; i < values.length; i++) values[i] = node.get(i).asDouble();
    return values;
  }

  private static double[][] matrix(JsonNode node) {
    var values = new double[node.size()][];
    for (int i = 0; i < values.length; i++) values[i] = vector(node.get(i));
    return values;
  }
}
