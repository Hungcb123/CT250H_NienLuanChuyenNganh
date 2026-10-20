package com.equifolio.ledger;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.*;
import org.springframework.jdbc.core.*;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.*;
import org.springframework.transaction.support.TransactionTemplate;
import java.math.*;
import java.sql.*;
import java.time.*;
import java.util.*;

@Service
public class PreparedPerformanceWorker {
    public static final int FORMULA_VERSION=1;
    private static final Logger log=LoggerFactory.getLogger(PreparedPerformanceWorker.class);
    private static final ZoneId ZONE=ZoneId.of("Asia/Ho_Chi_Minh");
    private final JdbcTemplate jdbc;
    private final NamedParameterJdbcTemplate named;
    private final ObjectMapper mapper;
    private final TransactionTemplate transaction;
    record Dirty(long user,long version,LocalDate revalue) {}
    record Value(BigDecimal nav,BigDecimal stock,BigDecimal gold,BigDecimal savings,BigDecimal cash,LocalDate priceDate,int missing) {}
    public PreparedPerformanceWorker(JdbcTemplate jdbc,ObjectMapper mapper,PlatformTransactionManager manager) {
        this.jdbc=jdbc;this.named=new NamedParameterJdbcTemplate(jdbc);this.mapper=mapper;
        transaction=new TransactionTemplate(manager);transaction.setIsolationLevel(TransactionDefinition.ISOLATION_REPEATABLE_READ);
    }

    @Scheduled(fixedDelay=5000,initialDelay=15000)
    public void runPending() {
        try { transaction.execute(status->{processBatch();return null;}); }
        catch(Exception e) {log.warn("[Prepared Performance] Batch rolled back ({})",e.getClass().getSimpleName());}
    }

    void processBatch() {
        Boolean locked=jdbc.queryForObject("SELECT pg_try_advisory_xact_lock(734922)",Boolean.class);
        if(!Boolean.TRUE.equals(locked))return;
        LocalDate today=LocalDate.now(ZONE);
        jdbc.execute("SELECT set_config('equifolio.performance_worker','on',true)");
        // Daily rollover and successful market-close completion are durable dependencies.
        jdbc.update("""
            INSERT INTO performance_dirty(user_id,dirty_from)
            SELECT u.id,? FROM users u LEFT JOIN performance_head h ON h.user_id=u.id
            WHERE NOT EXISTS(SELECT 1 FROM performance_dirty d WHERE d.user_id=u.id)
            AND (h.user_id IS NULL OR h.as_of_date<? OR h.formula_version<>?
                OR (h.provisional AND (SELECT count(*) FROM daily_market_sync_runs
                    WHERE sync_date=? AND status='SUCCESS' AND market IN ('STOCKS','GOLD'))=2))
            ON CONFLICT DO NOTHING
            """,today,today,FORMULA_VERSION,today);
        var dirty=jdbc.query("""
            SELECT user_id,input_version,revalue_from FROM performance_dirty
            WHERE retry_after<=now() ORDER BY requested_at LIMIT 12
            """,(rs,n)->new Dirty(rs.getLong(1),rs.getLong(2),rs.getDate(3)==null?null:rs.getDate(3).toLocalDate()));
        if(dirty.isEmpty())return;
        var ids=dirty.stream().map(Dirty::user).toList();
        var params=Map.<String,Object>of("ids",ids,"today",today);
        var benchmarkVersions=jdbc.query("SELECT generation FROM benchmark_head",(rs,n)->rs.getLong(1));
        Long benchmark=benchmarkVersions.isEmpty()?null:benchmarkVersions.getFirst();
        NavigableMap<LocalDate,BigDecimal> index=new TreeMap<>();
        if(benchmark!=null)jdbc.query("SELECT price_date,close FROM benchmark_daily WHERE generation=? ORDER BY price_date",
            (RowCallbackHandler)rs->index.put(rs.getDate(1).toLocalDate(),rs.getBigDecimal(2)),benchmark);

        Map<Long,List<PortfolioSnapshot>> histories=new HashMap<>();
        named.query("""
            SELECT * FROM portfolio_snapshots WHERE user_id IN (:ids) AND snapshot_date<=:today
            AND snapshot_source IN ('OBSERVED','DEMO') ORDER BY user_id,snapshot_date
            """,params,(RowCallbackHandler)rs->histories.computeIfAbsent(rs.getLong("user_id"),k->new ArrayList<>()).add(snapshot(rs)));
        Map<Long,NavigableMap<LocalDate,BigDecimal>> flows=new HashMap<>();
        named.query("""
            SELECT t.user_id,(t.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS flow_date,SUM(-e.amount) AS flow
            FROM transactions t JOIN entries e ON e.transaction_id=t.id JOIN accounts a ON a.id=e.account_id
            WHERE t.user_id IN (:ids) AND t.status='POSTED' AND a.account_code='EQUITY_CAPITAL'
            AND t.type IN ('CAPITAL_INJECTION','CAPITAL_WITHDRAWAL')
            GROUP BY t.user_id,flow_date ORDER BY t.user_id,flow_date
            """,params,(RowCallbackHandler)rs->flows.computeIfAbsent(rs.getLong(1),k->new TreeMap<>()).put(rs.getDate(2).toLocalDate(),rs.getBigDecimal(3)));
        Map<Long,Value> current=new HashMap<>();
        named.query("""
            WITH latest AS (SELECT DISTINCT ON(ticker) ticker,price,trade_date FROM market_prices
                WHERE trade_date<=:today ORDER BY ticker,trade_date DESC),
            valued AS (
              SELECT a.user_id,
                CASE WHEN a.account_code LIKE 'SAVINGS_%' OR b.asset_class='SAVINGS' THEN 'SAVINGS'
                     WHEN a.account_code='VND_WALLET' OR b.asset_class='CASH' THEN 'CASH' ELSE b.asset_class END AS kind,
                GREATEST(a.balance*CASE WHEN a.asset_type IN ('VND','EQUITY') THEN 1 ELSE p.price END,0) AS value,
                CASE WHEN a.balance>0 AND a.asset_type NOT IN ('VND','EQUITY') THEN p.trade_date END AS price_date,
                CASE WHEN a.balance>0 AND a.asset_type NOT IN ('VND','EQUITY') AND p.price IS NULL THEN 1 ELSE 0 END AS missing
              FROM accounts a JOIN assets b ON b.ticker=a.asset_type LEFT JOIN latest p ON p.ticker=a.asset_type
              WHERE a.user_id IN (:ids) AND a.account_code NOT IN ('TRADING_COSTS','EQUITY_CAPITAL','INTEREST_INCOME'))
            SELECT user_id,COALESCE(sum(value),0) AS nav,
                COALESCE(sum(value) FILTER(WHERE kind='STOCK'),0) AS stock,
                COALESCE(sum(value) FILTER(WHERE kind='GOLD'),0) AS gold,
                COALESCE(sum(value) FILTER(WHERE kind='SAVINGS'),0) AS savings,
                COALESCE(sum(value) FILTER(WHERE kind='CASH'),0) AS cash,
                min(price_date) AS price_date,sum(missing) AS missing FROM valued GROUP BY user_id
            """,params,(RowCallbackHandler)rs->current.put(rs.getLong("user_id"),value(rs)));
        Map<Long,Boolean> demo=new HashMap<>();
        named.query("SELECT id,username,email FROM users WHERE id IN (:ids)",params,(RowCallbackHandler)rs->{
            var user=new com.equifolio.profile.User();user.setUsername(rs.getString(2));user.setEmail(rs.getString(3));
            demo.put(rs.getLong(1),com.equifolio.common.DemoData.isDemoAccount(user));
        });
        Map<Long,Map<LocalDate,Value>> restated=revalueHistory(dirty,today,params);
        boolean finalized=jdbc.queryForObject("""
            SELECT count(*)=2 FROM daily_market_sync_runs WHERE sync_date=? AND status='SUCCESS' AND market IN ('STOCKS','GOLD')
            """,Boolean.class,today);
        var rates=jdbc.query("SELECT indicator_value FROM macro_indicators WHERE indicator_code='RF_INTERBANK_RATE' ORDER BY recorded_date DESC LIMIT 1",(rs,n)->rs.getDouble(1));
        double rf=rates.isEmpty()?4.5:rates.getFirst();
        for(var task:dirty) {
            try {
                var snaps=new ArrayList<>(histories.getOrDefault(task.user(),List.of()));
                for (var old : snaps) {
                    if (task.revalue()!=null && old.getSnapshotSource().equals("OBSERVED")
                            && !old.getSnapshotDate().isBefore(task.revalue()) && old.getSnapshotDate().isBefore(today)
                            && old.getTotalNav().signum()>0 && !restated.getOrDefault(task.user(),Map.of()).containsKey(old.getSnapshotDate()))
                        throw new IllegalStateException("Historical ledger is incomplete; kept last complete projection");
                }
                if(restated.getOrDefault(task.user(),Map.of()).values().stream().anyMatch(v->v.missing()>0))
                    throw new IllegalStateException("Missing historical prices; kept last complete projection");
                if(restated.containsKey(task.user()))for(var snap:snaps) {
                    Value corrected=restated.get(task.user()).get(snap.getSnapshotDate());
                    if(corrected!=null)apply(snap,corrected);
                }
                Value todayValue=current.getOrDefault(task.user(),new Value(BigDecimal.ZERO,BigDecimal.ZERO,BigDecimal.ZERO,BigDecimal.ZERO,BigDecimal.ZERO,null,0));
                if(todayValue.missing()>0)throw new IllegalStateException("Missing observed asset prices");
                snaps.removeIf(s->s.getSnapshotDate().equals(today));
                var snap=new PortfolioSnapshot();snap.setSnapshotDate(today);apply(snap,todayValue);
                boolean isDemo=demo.getOrDefault(task.user(),false);snap.setSnapshotSource(isDemo?"DEMO":"OBSERVED");
                snaps.add(snap);
                for(var s:snaps) {
                    var at=index.floorEntry(s.getSnapshotDate());
                    s.setVnindexValue(at==null?BigDecimal.ZERO:at.getValue());
                }
                var userFlows=flows.getOrDefault(task.user(),new TreeMap<>());
                var growth=PreparedPerformanceMath.growth(snaps,userFlows);
                var risk=PreparedPerformanceMath.risk(snaps,userFlows,rf,isDemo);
                Long generation=jdbc.queryForObject("SELECT nextval('performance_generation')",Long.class);
                List<Map<String,Object>> prepared=new ArrayList<>();
                for(var s:snaps) {
                    Map<String,Object> row=new LinkedHashMap<>();
                    row.put("date",s.getSnapshotDate().toString());row.put("nav",s.getTotalNav());row.put("stock",s.getStockValue());
                    row.put("gold",s.getGoldValue());row.put("savings",s.getSavingsValue());row.put("cash",s.getCashValue());
                    row.put("growth",growth.get(s.getSnapshotDate()).index());row.put("flow",growth.get(s.getSnapshotDate()).flow());
                    row.put("source",s.getSnapshotSource());prepared.add(row);
                }
                String json=mapper.writeValueAsString(prepared);
                jdbc.update("""
                    INSERT INTO performance_daily(user_id,generation,snapshot_date,nav,stock,gold,savings,cash,growth_index,external_flow)
                    SELECT ?,?,r.date,r.nav,r.stock,r.gold,r.savings,r.cash,r.growth,r.flow
                    FROM jsonb_to_recordset(?::jsonb) AS r(date date,nav numeric,stock numeric,gold numeric,savings numeric,cash numeric,growth numeric,flow numeric)
                    """,task.user(),generation,json);
                // Snapshot writes are exclusively background work; retain history for existing research consumers.
                jdbc.update("""
                    INSERT INTO portfolio_snapshots(user_id,snapshot_date,total_nav,stock_value,gold_value,savings_value,cash_value,vnindex_value,snapshot_source,valuation_status,price_as_of)
                    VALUES(?,?,?,?,?,?,?,0,?,?,?)
                    ON CONFLICT(user_id,snapshot_date) DO UPDATE SET total_nav=EXCLUDED.total_nav,stock_value=EXCLUDED.stock_value,
                    gold_value=EXCLUDED.gold_value,savings_value=EXCLUDED.savings_value,cash_value=EXCLUDED.cash_value,
                    snapshot_source=EXCLUDED.snapshot_source,valuation_status=EXCLUDED.valuation_status,price_as_of=EXCLUDED.price_as_of
                    """,task.user(),today,todayValue.nav(),todayValue.stock(),todayValue.gold(),todayValue.savings(),todayValue.cash(),
                    isDemo?"DEMO":"OBSERVED",finalized?"FINAL":"PROVISIONAL",todayValue.priceDate());
                for(var corrected:restated.getOrDefault(task.user(),Map.of()).entrySet()) {
                    var v=corrected.getValue();
                    jdbc.update("""
                        UPDATE portfolio_snapshots SET total_nav=?,stock_value=?,gold_value=?,savings_value=?,cash_value=?,
                        price_as_of=?,valuation_status='RESTATED' WHERE user_id=? AND snapshot_date=? AND snapshot_source='OBSERVED'
                        """,v.nav(),v.stock(),v.gold(),v.savings(),v.cash(),v.priceDate(),task.user(),corrected.getKey());
                }
                jdbc.update("""
                    INSERT INTO performance_head(user_id,generation,input_version,benchmark_generation,formula_version,as_of_date,price_as_of,provisional,data_kind,risk_payload)
                    VALUES(?,?,?,?,?,?,?,?,?,?::jsonb)
                    ON CONFLICT(user_id) DO UPDATE SET generation=EXCLUDED.generation,input_version=EXCLUDED.input_version,
                    benchmark_generation=EXCLUDED.benchmark_generation,formula_version=EXCLUDED.formula_version,generated_at=now(),
                    as_of_date=EXCLUDED.as_of_date,price_as_of=EXCLUDED.price_as_of,provisional=EXCLUDED.provisional,data_kind=EXCLUDED.data_kind,risk_payload=EXCLUDED.risk_payload
                    """,task.user(),generation,task.version(),benchmark,FORMULA_VERSION,today,todayValue.priceDate(),!finalized,isDemo?"DEMO":"OBSERVED",mapper.writeValueAsString(risk));
                jdbc.update("DELETE FROM performance_dirty WHERE user_id=? AND input_version=?",task.user(),task.version());
                jdbc.update("DELETE FROM performance_daily WHERE user_id=? AND generation<>?",task.user(),generation);
            } catch(IllegalStateException e) {
                jdbc.update("UPDATE performance_dirty SET last_error=?,retry_after=now()+interval '1 minute' WHERE user_id=? AND input_version=?",
                    e.getMessage(),task.user(),task.version());
                log.warn("[Prepared Performance] User {} deferred: {}",task.user(),e.getMessage());
            } catch(Exception e) {throw new IllegalStateException("Cannot prepare performance",e);}
        }
        jdbc.update("DELETE FROM benchmark_versions v WHERE NOT EXISTS(SELECT 1 FROM benchmark_head h WHERE h.generation=v.generation) AND NOT EXISTS(SELECT 1 FROM performance_head p WHERE p.benchmark_generation=v.generation)");
    }

    private Map<Long,Map<LocalDate,Value>> revalueHistory(List<Dirty> tasks,LocalDate today,Map<String,Object> params) {
        Map<Long,Map<LocalDate,Value>> result=new HashMap<>();
        if(tasks.stream().noneMatch(t->t.revalue()!=null&&t.revalue().isBefore(today)))return result;
        LocalDate from=tasks.stream().map(Dirty::revalue).filter(Objects::nonNull).min(LocalDate::compareTo).orElse(today);
        Map<String,Object> p=new HashMap<>(params);p.put("from",from);
        // Reconstruct only observed historical snapshots from posted entries, never today's holdings.
        named.query("""
            WITH positions AS (
              SELECT s.user_id,s.snapshot_date,a.account_code,a.asset_type,b.asset_class,SUM(e.amount) AS quantity
              FROM portfolio_snapshots s JOIN performance_dirty d ON d.user_id=s.user_id
              JOIN accounts a ON a.user_id=s.user_id JOIN assets b ON b.ticker=a.asset_type
              JOIN entries e ON e.account_id=a.id JOIN transactions t ON t.id=e.transaction_id
              WHERE s.user_id IN (:ids) AND s.snapshot_source='OBSERVED' AND s.snapshot_date>=:from AND s.snapshot_date>=d.revalue_from AND s.snapshot_date<:today
              AND t.status='POSTED' AND (t.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date<=s.snapshot_date
              AND a.account_code NOT IN ('TRADING_COSTS','EQUITY_CAPITAL','INTEREST_INCOME')
              GROUP BY s.user_id,s.snapshot_date,a.account_code,a.asset_type,b.asset_class
            ), valued AS (
              SELECT q.*,CASE WHEN q.account_code LIKE 'SAVINGS_%' OR asset_class='SAVINGS' THEN 'SAVINGS'
                WHEN q.account_code='VND_WALLET' OR asset_class='CASH' THEN 'CASH' ELSE asset_class END AS kind,
                GREATEST(quantity*CASE WHEN asset_type IN ('VND','EQUITY') THEN 1 ELSE p.price END,0) AS value,
                CASE WHEN quantity>0 AND asset_type NOT IN ('VND','EQUITY') THEN p.trade_date END AS price_date,
                CASE WHEN quantity>0 AND asset_type NOT IN ('VND','EQUITY') AND p.price IS NULL THEN 1 ELSE 0 END AS missing
              FROM positions q LEFT JOIN LATERAL(SELECT price,trade_date FROM market_prices WHERE ticker=q.asset_type
                AND trade_date<=q.snapshot_date ORDER BY trade_date DESC LIMIT 1)p ON TRUE
            )
            SELECT user_id,snapshot_date,COALESCE(sum(value),0) AS nav,
              COALESCE(sum(value) FILTER(WHERE kind='STOCK'),0) AS stock,
              COALESCE(sum(value) FILTER(WHERE kind='GOLD'),0) AS gold,
              COALESCE(sum(value) FILTER(WHERE kind='SAVINGS'),0) AS savings,
              COALESCE(sum(value) FILTER(WHERE kind='CASH'),0) AS cash,
              min(price_date) AS price_date,sum(missing) AS missing FROM valued GROUP BY user_id,snapshot_date
            """,p,(RowCallbackHandler)rs->{
                long uid=rs.getLong("user_id");var date=rs.getDate("snapshot_date").toLocalDate();
                var task=tasks.stream().filter(t->t.user()==uid).findFirst().orElseThrow();
                if(task.revalue()!=null&&!date.isBefore(task.revalue()))result.computeIfAbsent(uid,k->new TreeMap<>()).put(date,value(rs));
            });
        return result;
    }

    private static Value value(ResultSet rs) throws SQLException {
        var date=rs.getDate("price_date");
        return new Value(rs.getBigDecimal("nav"),rs.getBigDecimal("stock"),rs.getBigDecimal("gold"),rs.getBigDecimal("savings"),rs.getBigDecimal("cash"),date==null?null:date.toLocalDate(),rs.getInt("missing"));
    }
    private static PortfolioSnapshot snapshot(ResultSet rs) throws SQLException {
        var s=new PortfolioSnapshot();s.setSnapshotDate(rs.getDate("snapshot_date").toLocalDate());s.setSnapshotSource(rs.getString("snapshot_source"));
        s.setTotalNav(rs.getBigDecimal("total_nav"));s.setStockValue(Objects.requireNonNullElse(rs.getBigDecimal("stock_value"),BigDecimal.ZERO));s.setGoldValue(Objects.requireNonNullElse(rs.getBigDecimal("gold_value"),BigDecimal.ZERO));
        s.setSavingsValue(Objects.requireNonNullElse(rs.getBigDecimal("savings_value"),BigDecimal.ZERO));s.setCashValue(Objects.requireNonNullElse(rs.getBigDecimal("cash_value"),BigDecimal.ZERO));s.setVnindexValue(BigDecimal.ZERO);return s;
    }
    private static void apply(PortfolioSnapshot s,Value v) {
        s.setTotalNav(v.nav());s.setStockValue(v.stock());s.setGoldValue(v.gold());s.setSavingsValue(v.savings());s.setCashValue(v.cash());
    }
}
