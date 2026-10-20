package com.equifolio.optimizer;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.*;
import java.util.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/** Java features -> ONNX -> atomic forecast/EMA publication in the existing ledger. */
@Service
public class EmbeddedRegimeService {
  private static final Logger log=LoggerFactory.getLogger(EmbeddedRegimeService.class);
  private final ShockOnnxModel model;
  private final RegimeMarketData market;
  private final JdbcTemplate jdbc;
  private final TransactionTemplate transactions;
  private final ObjectMapper mapper;
  @Value("${ml.stock-model:shock-onnx}") private String engine="shock-onnx";

  public EmbeddedRegimeService(ShockOnnxModel model,RegimeMarketData market,JdbcTemplate jdbc,
      TransactionTemplate transactions,ObjectMapper mapper) {
    this.model=model;this.market=market;this.jdbc=jdbc;this.mapper=mapper;
    this.transactions=new TransactionTemplate(Objects.requireNonNull(transactions.getTransactionManager()));
    this.transactions.setPropagationBehavior(org.springframework.transaction.TransactionDefinition.PROPAGATION_REQUIRES_NEW);
  }

  public NativeRegimeForecast predict(int horizon) {return predict(horizon,ZonedDateTime.now(RegimeMarketData.ZONE));}
  NativeRegimeForecast predict(int horizon,ZonedDateTime now) {
    if(!Set.of(20,60,120).contains(horizon))return NativeRegimeForecast.unavailable("UNSUPPORTED_HORIZON");
    try {
      var snapshot=market.snapshot();
      var expected=RegimeMarketData.completedSession(now);
      if(snapshot.index().isEmpty()||!snapshot.index().getLast().date().equals(expected))
        return NativeRegimeForecast.unavailable("STALE_OR_INCOMPLETE_SESSION");
      int boundary=-1;
      for(int i=0;i<snapshot.index().size();i++)if(snapshot.index().get(i).date().equals(model.boundary(horizon)))boundary=i;
      if(boundary<0||snapshot.index().size()-1-boundary>=63)return NativeRegimeForecast.unavailable("REFIT_REQUIRED");
      var input=ShockFeatures.calculate(snapshot.index(),snapshot.etf(),model.names(horizon));
      return transactions.execute(status->publish(input,horizon));
    }catch(IllegalArgumentException e){
      String reason=e.getMessage();
      return NativeRegimeForecast.unavailable(reason!=null&&reason.matches("[A-Z_]{1,64}")?reason:"INVALID_MODEL_INPUT");
    }catch(Exception e){
      log.warn("Embedded ONNX prediction unavailable ({})",e.getClass().getSimpleName());
      return NativeRegimeForecast.unavailable("ONNX_UNAVAILABLE");
    }
  }

  private NativeRegimeForecast publish(ShockFeatures.Input input,int horizon) {
    try {
      String key=model.streamKey(horizon),bundle=model.digest(horizon);
      String fingerprint=ShockOnnxModel.hash(mapper.writeValueAsBytes(List.of(input.session().toString(),
          input.previousSession().toString(),input.features(),input.sigma())));
      String policy=mapper.writeValueAsString(Map.of("engine","onnxruntime-java","model_id",model.modelId(horizon),
          "bundle_sha256",bundle,"horizon_sessions",horizon,"feature_version","java-shock-features-v1"));
      jdbc.execute("SET LOCAL lock_timeout='15s'");
      jdbc.update("INSERT INTO ml_regime_streams(stream_key,asset,mode,policy) VALUES (?,'VNINDEX','live',?::jsonb) ON CONFLICT DO NOTHING",key,policy);
      var stream=jdbc.queryForMap("SELECT last_session,state FROM ml_regime_streams WHERE stream_key=? FOR UPDATE",key);
      var existing=jdbc.queryForList("SELECT input_sha256,bundle_sha256,previous_market_session,response FROM ml_regime_predictions WHERE stream_key=? AND session_date=?",key,input.session());
      if(!existing.isEmpty()) {
        var old=existing.getFirst();
        if(!fingerprint.equals(old.get("input_sha256"))||!bundle.equals(old.get("bundle_sha256"))
            ||!input.previousSession().equals(((java.sql.Date)old.get("previous_market_session")).toLocalDate()))
          throw new IllegalArgumentException("PREDICTION_CONFLICT");
        return mapper.readValue(old.get("response").toString(),NativeRegimeForecast.class);
      }
      LocalDate last=stream.get("last_session")==null?null:((java.sql.Date)stream.get("last_session")).toLocalDate();
      if(last!=null&&!input.session().isAfter(last))throw new IllegalArgumentException("OUT_OF_ORDER_SESSION");
      boolean contiguous=last!=null&&last.equals(input.previousSession())&&horizon==20;
      double[] previous=new double[3];
      if(stream.get("state")!=null) {
        var state=mapper.readTree(stream.get("state").toString());
        if(last==null||!last.toString().equals(state.path("last_session").asText())
            ||!bundle.equals(state.path("bundle_sha256").asText()))throw new IllegalArgumentException("INVALID_EMA_STATE");
        previous=mapper.convertValue(state.get("ema"),double[].class);ShockOnnxModel.validate(previous);
      }else if(last!=null)throw new IllegalArgumentException("INVALID_EMA_STATE");
      var prediction=model.predict(input,horizon,previous,contiguous);
      var scores=Arrays.stream(prediction.scores()).boxed().toList();
      var response=new NativeRegimeForecast(true,"READY",input.session().toString(),model.modelId(horizon),
          scores,scores.get(2)-scores.get(0),horizon==20&&!contiguous,bundle);
      String json=mapper.writeValueAsString(response);
      String state=mapper.writeValueAsString(Map.of("last_session",input.session().toString(),
          "bundle_sha256",bundle,"ema",prediction.ema()));
      jdbc.update("""
          INSERT INTO ml_regime_predictions(stream_key,session_date,previous_market_session,input_sha256,
            bundle_sha256,raw_scores,ema_scores,final_scores,response)
          VALUES (?,?,?,?,?,?::jsonb,?::jsonb,?::jsonb,?::jsonb)
          """,key,input.session(),input.previousSession(),fingerprint,bundle,
          mapper.writeValueAsString(prediction.raw()),mapper.writeValueAsString(prediction.ema()),mapper.writeValueAsString(scores),json);
      jdbc.update("UPDATE ml_regime_streams SET last_session=?,state=?::jsonb WHERE stream_key=?",input.session(),state,key);
      return response;
    }catch(RuntimeException e){throw e;}catch(Exception e){throw new IllegalStateException("ONNX publication failed",e);}
  }

  @Async @EventListener(ApplicationReadyEvent.class)
  public void start(){refresh();}

  @Scheduled(cron="0 */15 * * * *",zone="Asia/Ho_Chi_Minh")
  public synchronized void refresh() {
    if(!"shock-onnx".equals(engine))return;
    try {
      market.sync(RegimeMarketData.completedSession(ZonedDateTime.now(RegimeMarketData.ZONE)));
      for(int horizon:new int[]{20,60,120}) {
        var result=predict(horizon);
        if(!result.available())log.warn("ONNX T+{}: {}",horizon,result.status());
      }
    }catch(InterruptedException e){Thread.currentThread().interrupt();}
    catch(Exception e){log.warn("ONNX market sync deferred ({})",e.getClass().getSimpleName());}
  }
}
