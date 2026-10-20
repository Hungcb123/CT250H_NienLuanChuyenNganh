package com.equifolio.market;

import com.fasterxml.jackson.databind.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import java.net.URI;
import java.net.http.*;
import java.time.*;
import java.math.BigDecimal;
import java.util.*;

@Service
public class GoldHistorySync {
    private final GoldPriceStore store;
    private final ObjectMapper mapper;
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(6)).build();
    @Value("${market-data.vnappmob.api-key:}") private String key;
    @Value("${market-data.vnappmob.gold-url:https://vapi.vnappmob.com/api/v2/gold/sjc}") private String url;

    public GoldHistorySync(GoldPriceStore store, ObjectMapper mapper) { this.store = store; this.mapper = mapper; }

    public synchronized Map<String, Object> sync() {
        if (key == null || key.isBlank()) return Map.of("status", "NO_API_KEY", "source", "DATABASE");
        long now = Instant.now().getEpochSecond();
        var covered = store.coveredUntil();
        // After bootstrap, only fetch recent changes. Persisted cursor survives restarts.
        long from = covered.map(value -> Math.max(1, value - 2 * 86400)).orElse(1L);
        try {
            List<GoldObservation> observations = new ArrayList<>();
            fetchRange(from, now, observations, new int[]{64});
            // Latest endpoint includes the current session if date-range history lags.
            observations.addAll(parse(request(url), 0, now));
            if (observations.isEmpty()) throw new IllegalStateException("Provider returned no valid gold observations");
            if (!observations.stream().anyMatch(p -> p.ticker().equals("GOLD_SJC"))
                    || !observations.stream().anyMatch(p -> p.ticker().equals("GOLD_RING_9999"))) {
                throw new IllegalStateException("Provider response is missing a gold series");
            }
            store.save(observations, now);
            return Map.of("status", "SYNCED", "mode", covered.isEmpty() ? "BACKFILL" : "INCREMENTAL",
                    "observations", observations.size(), "source", GoldPriceStore.SOURCE);
        } catch (Exception e) {
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
            // A failed download never advances the cursor or creates a synthetic daily price.
            return Map.of("status", "STALE_DATABASE", "reason", "Provider sync failed; retained stored observations");
        }
    }

    private void fetchRange(long from, long to, List<GoldObservation> output, int[] budget) throws Exception {
        if (--budget[0] < 0) throw new IllegalStateException("History request budget exceeded");
        JsonNode payload = request(url + (url.contains("?") ? "&" : "?") + "date_from=" + from + "&date_to=" + to);
        JsonNode rows = payload.path("results");
        if (!rows.isArray()) throw new IllegalStateException("Invalid provider response");
        // Split dense ranges to avoid silently accepting a capped provider response.
        if (rows.size() >= 100 && to - from > 86400) {
            long middle = from + (to - from) / 2;
            fetchRange(from, middle, output, budget);
            fetchRange(middle + 1, to, output, budget);
        } else {
            output.addAll(parse(payload, from, to));
        }
    }

    private JsonNode request(String address) throws Exception {
        var request = HttpRequest.newBuilder(URI.create(address)).timeout(Duration.ofSeconds(12))
                .header("Authorization", "Bearer " + key).header("Accept", "application/json").GET().build();
        var response = client.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) throw new IllegalStateException("Gold provider HTTP " + response.statusCode());
        return mapper.readTree(response.body());
    }

    static List<GoldObservation> parse(JsonNode root, long from, long to) {
        List<GoldObservation> result = new ArrayList<>();
        if (!root.path("results").isArray()) throw new IllegalArgumentException("Missing results");
        for (JsonNode row : root.path("results")) {
            long timestamp = Long.parseLong(row.path("datetime").asText());
            if (timestamp < from || timestamp > to) throw new IllegalArgumentException("Provider ignored date bounds");
            Instant observed = Instant.ofEpochSecond(timestamp);
            // Provider returns these fields in VND per lượng; persist VND per chỉ.
            add(result, row, "GOLD_SJC", "buy_1l", "sell_1l", observed);
            add(result, row, "GOLD_RING_9999", "buy_nhan1c", "sell_nhan1c", observed);
        }
        return result;
    }

    private static void add(List<GoldObservation> out, JsonNode row, String ticker, String buyField, String sellField, Instant observed) {
        if (!row.hasNonNull(buyField) || !row.hasNonNull(sellField)) return;
        BigDecimal buy = new BigDecimal(row.get(buyField).asText()).movePointLeft(1);
        BigDecimal sell = new BigDecimal(row.get(sellField).asText()).movePointLeft(1);
        if (buy.signum() <= 0 || sell.compareTo(buy) < 0) throw new IllegalArgumentException("Invalid gold quote");
        out.add(new GoldObservation(ticker, buy, sell, observed));
    }
}
