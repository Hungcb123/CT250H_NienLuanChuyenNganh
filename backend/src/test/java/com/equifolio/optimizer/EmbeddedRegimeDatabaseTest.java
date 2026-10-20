package com.equifolio.optimizer;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.core.io.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.*;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.transaction.support.TransactionTemplate;

/** Runs only in an isolated schema; never mutates existing portfolio/model state. */
@EnabledIfEnvironmentVariable(named="EQUIFOLIO_ONNX_TEST_URL",matches="jdbc:postgresql:.*")
class EmbeddedRegimeDatabaseTest {
  @Test void concurrentPublicationRestartCarryResetAndRevisionsAreTransactional() throws Exception {
    String url=System.getenv("EQUIFOLIO_ONNX_TEST_URL");
    String user=System.getenv().getOrDefault("DB_USER","postgres"),password=System.getenv().getOrDefault("DB_PASSWORD","postgres");
    var admin=new JdbcTemplate(new DriverManagerDataSource(url,user,password));
    String schema="onnx_test_"+UUID.randomUUID().toString().replace("-","");
    admin.execute("CREATE SCHEMA "+schema);
    var mapper=new ObjectMapper();
    try(var model=new ModelHandle(mapper)) {
      var source=new DriverManagerDataSource(url+(url.contains("?")?"&":"?")+"currentSchema="+schema,user,password);
      new ResourceDatabasePopulator(new ClassPathResource("db/migration/V8__regime_prediction_ledger.sql"),
          new ClassPathResource("db/migration/V15__onnx_market_bars.sql")).execute(source);
      var jdbc=new JdbcTemplate(source);var tx=new TransactionTemplate(new DataSourceTransactionManager(source));
      var market=mock(RegimeMarketData.class);
      var seed=mapper.readTree(model.value.read("market_seed.json"));
      var index=new ArrayList<>(RegimeMarketData.readBars(seed.get("index")));
      var etf=new ArrayList<>(RegimeMarketData.readBars(seed.get("etf")));
      when(market.snapshot()).thenAnswer(inv->new RegimeMarketData.Snapshot(List.copyOf(index),List.copyOf(etf)));
      var service=new EmbeddedRegimeService(model.value,market,jdbc,tx,mapper);
      String key=model.value.streamKey(20);
      var date=index.getLast().date();var now=date.atTime(17,0).atZone(RegimeMarketData.ZONE);
      try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
        var tasks=new ArrayList<Future<NativeRegimeForecast>>();
        for(int i=0;i<6;i++)tasks.add(pool.submit(()->service.predict(20,now)));
        var first=tasks.getFirst().get(30,TimeUnit.SECONDS);
        assertTrue(first.available(),first.status());assertTrue(first.emaReset());
        for(var task:tasks)assertEquals(first,task.get(30,TimeUnit.SECONDS));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM ml_regime_predictions",Integer.class));
        assertEquals(first,new EmbeddedRegimeService(model.value,market,jdbc,tx,mapper).predict(20,now));
      }
      // Publication owns a write transaction even when the calling API is
      // inside a read-only transaction that subsequently rolls back.
      tx.setReadOnly(true);
      var independent=tx.execute(status->{status.setRollbackOnly();return service.predict(60,now);});
      assertTrue(independent.available(),independent.status());
      assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM ml_regime_predictions WHERE stream_key=?",Integer.class,model.value.streamKey(60)));
      double[] previous=mapper.convertValue(mapper.readTree(jdbc.queryForObject("SELECT state::text FROM ml_regime_streams WHERE stream_key=?",String.class,key)).get("ema"),double[].class);
      append(index,etf,date.plusDays(1));
      var input=ShockFeatures.calculate(index,etf,model.value.names(20));
      var expected=model.value.predict(input,20,previous,true);
      var carried=service.predict(20,index.getLast().date().atTime(17,0).atZone(RegimeMarketData.ZONE));
      assertTrue(carried.available(),carried.status());assertFalse(carried.emaReset());
      assertArrayEquals(expected.scores(),carried.classScores().stream().mapToDouble(Double::doubleValue).toArray(),1e-12);
      // Skip publication of the next observed session: the following one resets.
      append(index,etf,LocalDate.parse("2026-10-05"));append(index,etf,LocalDate.parse("2026-10-06"));
      var reset=service.predict(20,LocalDate.parse("2026-10-06").atTime(17,0).atZone(RegimeMarketData.ZONE));
      assertTrue(reset.available(),reset.status());assertTrue(reset.emaReset());
      var old=index.removeLast();index.add(new ShockFeatures.Bar(old.date(),old.close()+.1,old.open(),old.high(),old.low(),old.volume()));
      var revised=service.predict(20,old.date().atTime(17,0).atZone(RegimeMarketData.ZONE));
      assertFalse(revised.available());assertEquals("PREDICTION_CONFLICT",revised.status());
      assertEquals(3,jdbc.queryForObject("SELECT count(*) FROM ml_regime_predictions WHERE stream_key=?",Integer.class,key));
      assertEquals("STALE_OR_INCOMPLETE_SESSION",service.predict(20,old.date().plusDays(1).atTime(17,0).atZone(RegimeMarketData.ZONE)).status());
      for(int i=0;i<70;i++){var next=index.getLast().date().plusDays(1);while(next.getDayOfWeek().getValue()>5)next=next.plusDays(1);append(index,etf,next);}
      assertEquals("REFIT_REQUIRED",service.predict(20,index.getLast().date().atTime(17,0).atZone(RegimeMarketData.ZONE)).status());
    }finally{admin.execute("DROP SCHEMA "+schema+" CASCADE");}
  }
  private static void append(List<ShockFeatures.Bar> index,List<ShockFeatures.Bar> etf,LocalDate date) {
    double close=index.getLast().close()*1.002,e=etf.getLast().close()*1.001;
    index.add(new ShockFeatures.Bar(date,close,close*.999,close*1.01,close*.99,1e9));
    etf.add(new ShockFeatures.Bar(date,e,e,e,e,1e6));
  }
  private static class ModelHandle implements AutoCloseable {
    final ShockOnnxModel value;
    ModelHandle(ObjectMapper mapper){value=new ShockOnnxModel(new DefaultResourceLoader(),mapper,"classpath:models/shock/");}
    public void close(){value.close();}
  }
}
