package com.equifolio.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

@Repository
public class BenchmarkStore {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    public BenchmarkStore(JdbcTemplate jdbc,ObjectMapper mapper) {this.jdbc=jdbc;this.mapper=mapper;}
    @Transactional
    public void publish(List<Map<String,Object>> history) {
        try {
            var rows=history.stream().map(p->Map.of("date",p.get("date"),"close",p.get("close"))).toList();
            String json=mapper.writeValueAsString(rows);
            String checksum=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(json.getBytes(StandardCharsets.UTF_8)));
            jdbc.execute("SELECT pg_advisory_xact_lock(734921)");
            var current=jdbc.query("SELECT v.checksum FROM benchmark_head h JOIN benchmark_versions v USING(generation)",(rs,n)->rs.getString(1));
            if(!current.isEmpty()&&checksum.equals(current.getFirst()))return;
            Long version=jdbc.queryForObject("SELECT nextval('benchmark_generation')",Long.class);
            jdbc.update("INSERT INTO benchmark_versions(generation,checksum) VALUES (?,?)",version,checksum);
            jdbc.update("""
                INSERT INTO benchmark_daily(generation,price_date,close)
                SELECT ?,r.date,r.close FROM jsonb_to_recordset(?::jsonb) AS r(date date,close numeric)
                """,version,json);
            jdbc.update("""
                INSERT INTO performance_dirty(user_id,dirty_from)
                SELECT id,COALESCE((SELECT min(price_date) FROM benchmark_daily WHERE generation=?),CURRENT_DATE) FROM users
                ON CONFLICT(user_id) DO UPDATE SET input_version=nextval('performance_input_version'),
                dirty_from=LEAST(performance_dirty.dirty_from,EXCLUDED.dirty_from),requested_at=now(),retry_after=now()
                """,version);
            jdbc.update("INSERT INTO benchmark_head(singleton,generation) VALUES (true,?) ON CONFLICT(singleton) DO UPDATE SET generation=EXCLUDED.generation",version);
        } catch (RuntimeException e) {throw e;} catch(Exception e) {throw new IllegalStateException("Could not publish benchmark",e);}
    }
}
