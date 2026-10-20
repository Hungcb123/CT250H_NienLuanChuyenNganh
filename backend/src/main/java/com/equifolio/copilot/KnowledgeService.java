package com.equifolio.copilot;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class KnowledgeService {
  private final JdbcTemplate jdbc;
  private final ObjectMapper json;

  @Value("${knowledge.embedding-url:}")
  private String embeddingUrl = "";

  @Value("${knowledge.embedding-model:}")
  private String embeddingModel = "";

  @Value("${knowledge.embedding-key:}")
  private String embeddingKey = "";

  public KnowledgeService(JdbcTemplate jdbc, ObjectMapper json) {
    this.jdbc = jdbc;
    this.json = json;
  }

  public record Source(
      String id,
      String title,
      String source,
      int chunk,
      String content,
      double score,
      String retrievalMode) {}

  public record Document(String title, String source, String content) {}

  public Map<String, Object> status() {
    return Map.of(
        "retrievalMode",
        embeddingUrl.isBlank() ? "FULL_TEXT" : "HYBRID_RRF",
        "embeddingModel",
        embeddingModel,
        "dimensions",
        1536,
        "privateDocuments",
        true);
  }

  @Transactional
  public int ingest(Long user, Document document) {
    if (document.title() == null
        || document.title().isBlank()
        || document.title().length() > 120
        || document.source() == null
        || document.source().length() > 500
        || document.content() == null
        || document.content().isBlank()
        || document.content().length() > 40000)
      throw new IllegalArgumentException("Tên tối đa 120 ký tự, nguồn 500, nội dung 1–40000 ký tự");
    int count = 0;
    for (int start = 0; start < document.content().length(); start += 900) {
      String chunk =
          document.content().substring(start, Math.min(start + 1100, document.content().length()));
      float[] vector = embed(chunk);
      try {
        String metadata =
            json.writeValueAsString(
                Map.of(
                    "owner",
                    user,
                    "title",
                    document.title(),
                    "source",
                    document.source(),
                    "chunk",
                    count,
                    "embeddingModel",
                    embeddingModel));
        UUID id =
            UUID.nameUUIDFromBytes(
                (user + ":" + document.source() + ":" + document.title() + ":" + count)
                    .getBytes(StandardCharsets.UTF_8));
        jdbc.update(
            """
INSERT INTO vector_store(id,content,metadata,embedding,search_tsv)
VALUES(?,?,?::jsonb,?::vector,to_tsvector('simple',unaccent(?)))
ON CONFLICT(id) DO UPDATE SET content=excluded.content,metadata=excluded.metadata,embedding=excluded.embedding,search_tsv=excluded.search_tsv
""",
            id,
            chunk,
            metadata,
            vector == null ? null : Arrays.toString(vector),
            chunk);
        count++;
      } catch (java.io.IOException ex) {
        throw new IllegalStateException("Không thể lưu metadata", ex);
      }
      if (start + 1100 >= document.content().length()) break;
    }
    // Re-ingestion of a shorter document must not leave old trailing chunks searchable.
    jdbc.update(
        "DELETE FROM vector_store WHERE metadata->>'owner'=? AND metadata->>'source'=? AND"
            + " metadata->>'title'=? AND (metadata->>'chunk')::int>=?",
        user.toString(),
        document.source(),
        document.title(),
        count);
    return count;
  }

  public List<Source> search(Long user, String query) {
    if (query == null || query.isBlank()) return List.of();
    if (query.length() > 2000) throw new IllegalArgumentException("Câu hỏi tối đa 2000 ký tự");
    float[] embedding = null;
    String mode = "FULL_TEXT";
    try {
      embedding = embed(query);
      if (embedding != null) mode = "HYBRID_RRF";
    } catch (IllegalStateException ex) {
      mode = "FULL_TEXT_EMBEDDING_UNAVAILABLE";
    }
    String access = "(metadata->>'owner' IS NULL OR metadata->>'owner'=?)";
    String sql =
        """
WITH lexical AS (
  SELECT id,row_number() OVER(ORDER BY ts_rank_cd(search_tsv,websearch_to_tsquery('simple',unaccent(?))) DESC,id) AS rank
  FROM vector_store WHERE %s AND search_tsv @@ websearch_to_tsquery('simple',unaccent(?)) ORDER BY rank LIMIT 30
)
"""
            .formatted(access);
    List<Object> args = new ArrayList<>(List.of(query, user.toString(), query));
    if (embedding != null) {
      sql +=
          """
, semantic AS (
   SELECT id,row_number() OVER(ORDER BY embedding <=> ?::vector,id) AS rank
   FROM vector_store WHERE %s AND embedding IS NOT NULL AND metadata->>'embeddingModel'=?
   ORDER BY embedding <=> ?::vector,id LIMIT 30
), ranked AS (
   SELECT id,SUM(score) AS score FROM (
     SELECT id,1.0/(60+rank) AS score FROM lexical UNION ALL SELECT id,1.0/(60+rank) FROM semantic
   ) r GROUP BY id
)
"""
              .formatted(access);
      args.add(Arrays.toString(embedding));
      args.add(user.toString());
      args.add(embeddingModel);
      args.add(Arrays.toString(embedding));
    } else sql += ", ranked AS (SELECT id,1.0/(60+rank) AS score FROM lexical) ";
    sql +=
        "SELECT v.id,v.content,v.metadata,r.score FROM ranked r JOIN vector_store v ON v.id=r.id"
            + " ORDER BY r.score DESC,v.id LIMIT 5";
    final String retrievalMode = mode;
    return jdbc.query(
        sql,
        (rs, i) -> {
          try {
            var meta =
                json.readTree(rs.getString("metadata") == null ? "{}" : rs.getString("metadata"));
            return new Source(
                rs.getString("id"),
                meta.path("title").asText("Cẩm nang tài chính"),
                meta.path("source").asText("Tài liệu hệ thống"),
                meta.path("chunk").asInt(0),
                rs.getString("content"),
                rs.getDouble("score"),
                retrievalMode);
          } catch (java.io.IOException ex) {
            throw new IllegalStateException("Metadata không hợp lệ", ex);
          }
        },
        args.toArray());
  }

  private float[] embed(String text) {
    if (embeddingUrl.isBlank()) return null;
    if (embeddingModel.isBlank()) throw new IllegalStateException("Chưa cấu hình embedding model");
    try {
      var request =
          HttpRequest.newBuilder(URI.create(embeddingUrl))
              .timeout(Duration.ofSeconds(20))
              .header("Content-Type", "application/json");
      if (!embeddingKey.isBlank()) request.header("Authorization", "Bearer " + embeddingKey);
      var response =
          HttpClient.newBuilder()
              .connectTimeout(Duration.ofSeconds(5))
              .build()
              .send(
                  request
                      .POST(
                          HttpRequest.BodyPublishers.ofString(
                              json.writeValueAsString(
                                  Map.of("model", embeddingModel, "input", text))))
                      .build(),
                  HttpResponse.BodyHandlers.ofString());
      if (response.statusCode() != 200)
        throw new IllegalStateException("Embedding provider không sẵn sàng");
      var vector = json.readTree(response.body()).path("data").path(0).path("embedding");
      if (vector.size() != 1536) throw new IllegalStateException("Embedding phải có 1536 chiều");
      float[] out = new float[1536];
      double norm = 0;
      for (int i = 0; i < out.length; i++) {
        if (!vector.get(i).isNumber()) throw new IllegalStateException("Embedding không hợp lệ");
        out[i] = (float) vector.get(i).asDouble();
        if (!Float.isFinite(out[i])) throw new IllegalStateException("Embedding không hợp lệ");
        norm += out[i] * out[i];
      }
      if (norm == 0) throw new IllegalStateException("Embedding bằng 0");
      return out;
    } catch (InterruptedException ex) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException("Embedding bị gián đoạn", ex);
    } catch (java.io.IOException ex) {
      throw new IllegalStateException("Không kết nối được embedding provider", ex);
    }
  }
}
