package com.equifolio.optimizer;

import ai.onnxruntime.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PreDestroy;
import java.nio.DoubleBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ResourceLoader;
import org.springframework.stereotype.Service;

/** Complete frozen ensemble in-process; no Python worker or HTTP inference. */
@Service
public class ShockOnnxModel {
  public record Prediction(double[] scores, double[] ema, double[] raw) {}
  private final OrtEnvironment environment=OrtEnvironment.getEnvironment();
  private final Map<Integer,OrtSession> sessions=new HashMap<>();
  private final Map<Integer,JsonNode> contracts=new HashMap<>();
  private final Map<String,String> checksums=new HashMap<>();
  private final String directory;
  private final ResourceLoader resources;
  private final ObjectMapper mapper;

  public ShockOnnxModel(ResourceLoader resources, ObjectMapper mapper,
      @Value("${ml.shock-directory:classpath:models/shock/}") String directory) {
    this.resources=resources;this.mapper=mapper;
    this.directory=directory.endsWith("/")?directory:directory+"/";
    try {
      var manifest=mapper.readTree(read("checksums.json"));
      for(var entries=manifest.fields();entries.hasNext();) {
        var entry=entries.next();
        if(!entry.getKey().matches("[a-zA-Z0-9_.]+"))throw new IllegalStateException("Invalid model payload path");
        String digest=hash(read(entry.getKey()));
        if(!digest.equals(entry.getValue().asText()))throw new IllegalStateException("ONNX checksum mismatch: "+entry.getKey());
        checksums.put(entry.getKey(),digest);
      }
      if(!checksums.containsKey("market_seed.json"))throw new IllegalStateException("Missing reviewed market seed checksum");
      for(int h:new int[]{20,60,120}) {
        String model=h==20?"shock_regime.onnx":"regime_t"+h+".onnx";
        String contract=h==20?"contract.json":"regime_t"+h+".json";
        if(!checksums.containsKey(model)||!checksums.containsKey(contract))throw new IllegalStateException("Incomplete ONNX bundle");
        contracts.put(h,mapper.readTree(read(contract)));
        try(var options=new OrtSession.SessionOptions()) {
          options.setIntraOpNumThreads(2);options.setInterOpNumThreads(1);
          sessions.put(h,environment.createSession(read(model),options));
        }
      }
      if(contracts.get(20).path("class_scores_are_probabilities").asBoolean(true)
          || names(20).size()!=45)throw new IllegalStateException("Invalid shock model contract");
    } catch(Exception e) {
      close();throw new IllegalStateException("Cannot load packaged ONNX models",e);
    }
  }

  byte[] read(String name) throws java.io.IOException {
    try(var input=resources.getResource(directory+name).getInputStream()) {return input.readAllBytes();}
  }
  public List<String> names(int horizon) {
    var result=new ArrayList<String>();contracts.get(horizon).path("features").forEach(v->result.add(v.asText()));return List.copyOf(result);
  }
  public LocalDate boundary(int horizon) {return LocalDate.parse(contracts.get(horizon).path("boundary").asText());}
  public String digest(int horizon) {
    String model=horizon==20?"shock_regime.onnx":"regime_t"+horizon+".onnx";
    String contract=horizon==20?"contract.json":"regime_t"+horizon+".json";
    return hash((checksums.get(model)+checksums.get(contract)).getBytes(StandardCharsets.UTF_8));
  }
  public String streamKey(int horizon) {
    return hash(("java-shock-features-v1:VNINDEX:"+horizon+":"+digest(horizon)).getBytes(StandardCharsets.UTF_8));
  }
  public String modelId(int horizon) {return horizon==20?"shock_shrink_onnx_v1":"experimental-close-etf-onnx-v1-T"+horizon;}

  public Prediction predict(ShockFeatures.Input input,int horizon,double[] previous,boolean contiguous) throws OrtException {
    if(!sessions.containsKey(horizon)||input.features().length!=names(horizon).size()
        ||!Double.isFinite(input.sigma())||input.sigma()<=0)throw new IllegalArgumentException("INVALID_MODEL_INPUT");
    for(double v:input.features())if(!Double.isFinite(v))throw new IllegalArgumentException("INVALID_MODEL_INPUT");
    if(horizon!=20) {
      float[][] values=new float[1][input.features().length];
      for(int i=0;i<values[0].length;i++)values[0][i]=(float)input.features()[i];
      try(var tensor=OnnxTensor.createTensor(environment,values);
          var result=sessions.get(horizon).run(Map.of("input",tensor))) {
        float[] probs=((float[][])result.get(1).getValue())[0];
        double[] score=new double[]{probs[0],probs[1],probs[2]};
        double sum=Arrays.stream(score).sum();for(int i=0;i<3;i++)score[i]/=sum;
        validate(score);return new Prediction(score,score.clone(),score.clone());
      }
    }
    if(previous.length!=3)throw new IllegalArgumentException("INVALID_EMA_STATE");
    for(double v:previous)if(!Double.isFinite(v))throw new IllegalArgumentException("INVALID_EMA_STATE");
    if(contiguous)validate(previous);
    double[] parameters=mapper.convertValue(contracts.get(20).get("parameters"),double[].class);
    try(var features=OnnxTensor.createTensor(environment,new double[][]{input.features()});
        var sigma=OnnxTensor.createTensor(environment,DoubleBuffer.wrap(new double[]{input.sigma()}),new long[]{1});
        var params=OnnxTensor.createTensor(environment,DoubleBuffer.wrap(parameters),new long[]{3});
        var ema=OnnxTensor.createTensor(environment,new double[][]{previous});
        var carry=OnnxTensor.createTensor(environment,contiguous);
        var result=sessions.get(20).run(Map.of("features",features,"horizon_sigma",sigma,"parameters",params,
            "previous_ema",ema,"contiguous",carry),Set.of("class_scores","ema"))) {
      double[] scores=((double[][])result.get("class_scores").orElseThrow().getValue())[0];
      double[] next=((double[][])result.get("ema").orElseThrow().getValue())[0];
      double[] raw=new double[3];for(int i=0;i<3;i++)raw[i]=2*scores[i]-next[i];
      validate(scores);validate(next);validate(raw);
      return new Prediction(scores,next,raw);
    }
  }
  static void validate(double[] score) {
    if(score.length!=3)throw new IllegalArgumentException("INVALID_SCORES");
    double sum=0;for(double v:score){if(!Double.isFinite(v)||v<0||v>1)throw new IllegalArgumentException("INVALID_SCORES");sum+=v;}
    if(Math.abs(sum-1)>1e-9)throw new IllegalArgumentException("INVALID_SCORES");
  }
  static String hash(byte[] bytes) {
    try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    catch(java.security.NoSuchAlgorithmException e){throw new IllegalStateException(e);}
  }
  @PreDestroy public void close() {
    for(var session:sessions.values())try{session.close();}catch(OrtException ignored){}
    sessions.clear();
  }
}
