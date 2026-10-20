package com.equifolio.optimizer;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.*;
import java.util.ArrayList;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class NativeRegimeService {
  @org.springframework.beans.factory.annotation.Autowired(required=false)
  private EmbeddedRegimeService embedded;
  @Value("${ml.stock-model:shock-onnx}")
  private String engine = "native";
  private final URI uri;
  private final String token;
  private final ObjectMapper mapper;
  private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();

  public NativeRegimeService(@Value("${ml.native-url:http://127.0.0.1:8091}") String url,
                            @Value("${ml.native-token:}") String token, ObjectMapper mapper) {
    this.uri = URI.create(url.replaceAll("/+$", "") + "/v1/predict");
    this.token = token;
    this.mapper = mapper;
  }

  public NativeRegimeForecast predict() { return predict(20); }

  public NativeRegimeForecast predict(int horizon) {
    if ("shock-onnx".equals(engine))
      return embedded == null ? NativeRegimeForecast.unavailable("ONNX_UNAVAILABLE") : embedded.predict(horizon);
    if (!java.util.Set.of(20,60,120).contains(horizon)) return NativeRegimeForecast.unavailable("UNSUPPORTED_HORIZON");
    try {
      var request = HttpRequest.newBuilder(horizon == 20 ? uri : URI.create(uri + "?horizon=" + horizon)).timeout(Duration.ofSeconds(25))
          .POST(HttpRequest.BodyPublishers.noBody());
      if (!token.isBlank()) request.header("Authorization", "Bearer " + token);
      var response = http.send(request.build(), HttpResponse.BodyHandlers.ofString());
      JsonNode json = mapper.readTree(response.body());
      if (response.statusCode() != 200) {
        String status = json.path("status").asText("WORKER_UNAVAILABLE");
        return NativeRegimeForecast.unavailable(status.matches("[A-Z_]{1,64}") ? status : "WORKER_UNAVAILABLE");
      }
      if (!"READY".equals(json.path("status").asText())
          || !"VNINDEX".equals(json.path("asset").asText())
          || !"live".equals(json.path("mode").asText())
          || json.path("horizon_sessions").asInt() != horizon
          || !"class_balanced_decision_scores_not_probabilities".equals(json.path("score_semantics").asText()))
        return NativeRegimeForecast.unavailable("INVALID_CONTRACT");
      var scores = json.path("class_scores");
      if (!scores.isArray() || scores.size() != 3) return NativeRegimeForecast.unavailable("INVALID_SCORES");
      var values = new ArrayList<Double>();
      double sum = 0;
      for (var score : scores) {
        if (!score.isNumber()) return NativeRegimeForecast.unavailable("INVALID_SCORES");
        double value = score.doubleValue();
        if (!Double.isFinite(value) || value < 0 || value > 1) return NativeRegimeForecast.unavailable("INVALID_SCORES");
        values.add(value); sum += value;
      }
      if (Math.abs(sum - 1) > 1e-9) return NativeRegimeForecast.unavailable("INVALID_SCORES");
      double net = values.get(2) - values.get(0);
      if (!json.path("net_score").isNumber() || Math.abs(net - json.path("net_score").doubleValue()) > 1e-9)
        return NativeRegimeForecast.unavailable("INVALID_NET_SCORE");
      var today = LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh"));
      var session = LocalDate.parse(json.path("session").asText());
      if (session.isAfter(today) || session.isBefore(today.minusDays(4))) return NativeRegimeForecast.unavailable("STALE_SESSION");
      var result = new NativeRegimeForecast(true, "READY", session.toString(), json.path("model_id").asText(),
          java.util.List.copyOf(values), net, json.path("ema_reset").asBoolean(), json.path("bundle_sha256").asText());
      if (!json.path("signal").isInt() || result.signal() != json.path("signal").asInt())
        return NativeRegimeForecast.unavailable("INVALID_SIGNAL");
      return result;
    } catch (InterruptedException exception) {
      Thread.currentThread().interrupt();
      return NativeRegimeForecast.unavailable("WORKER_INTERRUPTED");
    } catch (Exception exception) {
      return NativeRegimeForecast.unavailable("WORKER_UNAVAILABLE");
    }
  }
}
