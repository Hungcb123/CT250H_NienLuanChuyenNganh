package com.equifolio.market;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;
import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.util.*;

@Repository
public class GoldPriceStore {
    static final String SOURCE = "VnAppMob";
    private final JdbcTemplate jdbc;
    public GoldPriceStore(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    public Optional<Long> coveredUntil() {
        return jdbc.query("SELECT covered_until FROM gold_sync_state WHERE provider=?", (rs, n) -> rs.getLong(1), SOURCE).stream().findFirst();
    }

    @Transactional
    public void save(List<GoldObservation> rows, long coveredUntil) {
        for (var row : rows.stream().sorted(Comparator.comparing(GoldObservation::observedAt)).toList()) {
            jdbc.update("""
                INSERT INTO gold_price_observations(ticker,trade_date,buy_price,sell_price,observed_at,source)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(ticker,trade_date) DO UPDATE SET
                  buy_price=EXCLUDED.buy_price,sell_price=EXCLUDED.sell_price,
                  observed_at=EXCLUDED.observed_at,source=EXCLUDED.source,fetched_at=CURRENT_TIMESTAMP
                WHERE gold_price_observations.observed_at <= EXCLUDED.observed_at
                """, row.ticker(), row.date(), row.buy(), row.sell(), Timestamp.from(row.observedAt()), SOURCE);
            // Existing portfolio valuation keeps using market_prices, now with verified prices.
            jdbc.update("""
                INSERT INTO market_prices(ticker,trade_date,price,updated_at)
                SELECT ticker,trade_date,sell_price,CURRENT_TIMESTAMP
                FROM gold_price_observations WHERE ticker=? AND trade_date=?
                ON CONFLICT(ticker,trade_date) DO UPDATE SET price=EXCLUDED.price,updated_at=EXCLUDED.updated_at
                """, row.ticker(), row.date());
        }
        jdbc.update("""
            INSERT INTO gold_sync_state(provider,covered_until) VALUES (?,?)
            ON CONFLICT(provider) DO UPDATE SET
            covered_until=GREATEST(gold_sync_state.covered_until,EXCLUDED.covered_until),updated_at=CURRENT_TIMESTAMP
            """, SOURCE, coveredUntil);
    }

    public record Bar(LocalDate date, BigDecimal close) {}
    public List<Bar> history(String ticker) {
        return jdbc.query("SELECT trade_date,sell_price FROM gold_price_observations WHERE ticker=? ORDER BY trade_date",
                (rs, n) -> new Bar(rs.getDate(1).toLocalDate(), rs.getBigDecimal(2)), ticker);
    }

    public List<GoldPriceDTO> latest() {
        return jdbc.query("""
            SELECT ticker,buy_price,sell_price,source,trade_date FROM (
                SELECT *,row_number() OVER (PARTITION BY ticker ORDER BY trade_date DESC) AS rank
                FROM gold_price_observations
            ) latest WHERE rank <= 2 ORDER BY ticker,trade_date DESC
            """, rs -> {
                Map<String, GoldPriceDTO> result = new LinkedHashMap<>();
                while (rs.next()) {
                    String ticker = rs.getString("ticker");
                    BigDecimal sell = rs.getBigDecimal("sell_price");
                    if (!result.containsKey(ticker)) {
                        result.put(ticker, new GoldPriceDTO(ticker, ticker.equals("GOLD_SJC") ? "Vàng miếng SJC 999.9" : "Vàng nhẫn trơn 999.9",
                                rs.getBigDecimal("buy_price"), sell, null, null, rs.getString("source"), rs.getDate("trade_date").toLocalDate()));
                    } else {
                        var current = result.get(ticker);
                        double change = current.sellPrice().subtract(sell).doubleValue();
                        result.put(ticker, new GoldPriceDTO(current.ticker(), current.name(), current.buyPrice(), current.sellPrice(),
                                change, change / sell.doubleValue() * 100, current.source(), current.tradeDate()));
                    }
                }
                return new ArrayList<>(result.values());
            });
    }
}
