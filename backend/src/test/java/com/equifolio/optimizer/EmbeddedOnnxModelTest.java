package com.equifolio.optimizer;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.core.io.DefaultResourceLoader;
import org.springframework.test.util.ReflectionTestUtils;

class EmbeddedOnnxModelTest {
  private static ShockOnnxModel model;
  private static final ObjectMapper mapper=new ObjectMapper();
  @BeforeAll static void load(){model=new ShockOnnxModel(new DefaultResourceLoader(),mapper,"classpath:models/shock/");}
  @AfterAll static void close(){if(model!=null)model.close();}

  @Test void rawMarketBarsThroughJavaAndOnnxMatchNativePython() throws Exception {
    var seed=mapper.readTree(model.read("market_seed.json"));
    var index=RegimeMarketData.readBars(seed.get("index"));var etf=RegimeMarketData.readBars(seed.get("etf"));
    var cases=mapper.readTree(getClass().getResourceAsStream("/models/shock_raw_inference_cases.json"));
    for(var row:cases) {
      int end=0;while(!index.get(end).date().toString().equals(row.get("session").asText()))end++;
      var input=ShockFeatures.calculate(index.subList(0,end+1),etf,model.names(20));
      var actual=model.predict(input,20,new double[3],false);
      var expected=mapper.convertValue(row.get("class_scores"),double[].class);
      assertArrayEquals(expected,actual.scores(),1e-5,row.get("session").asText());
      int best=0;for(int i=1;i<3;i++)if(actual.scores()[i]>actual.scores()[best])best=i;
      assertEquals(row.get("signal").asInt(),best-1);
    }
  }

  @Test void packagedLongHorizonsMatchPythonFixturesAndHaveSeparateStreams() throws Exception {
    assertNotEquals(model.streamKey(20),model.streamKey(60));assertNotEquals(model.streamKey(60),model.streamKey(120));
    for(int h:new int[]{60,120}) {
      var contract=mapper.readTree(model.read("regime_t"+h+".json"));
      var fixture=contract.get("fixture");
      var input=new ShockFeatures.Input(model.boundary(h),model.boundary(h).minusDays(1),
          mapper.convertValue(fixture.get("features"),double[].class),.1);
      var actual=model.predict(input,h,new double[3],false);
      assertArrayEquals(mapper.convertValue(fixture.get("class_scores"),double[].class),actual.scores(),1e-5);
      assertTrue(contract.get("experimental").asBoolean());
    }
  }

  @Test void productionRoutingUsesEmbeddedEngineWithNoWorkerConnection() {
    var embedded=mock(EmbeddedRegimeService.class);
    var ready=new NativeRegimeForecast(true,"READY","2026-10-01","shock_shrink_onnx_v1",List.of(.2,.3,.5),.3,true,"a".repeat(64));
    when(embedded.predict(20)).thenReturn(ready);
    var service=new NativeRegimeService("http://127.0.0.1:1","",mapper);
    ReflectionTestUtils.setField(service,"engine","shock-onnx");ReflectionTestUtils.setField(service,"embedded",embedded);
    assertSame(ready,service.predict());verify(embedded).predict(20);
    ReflectionTestUtils.setField(service,"embedded",null);
    assertEquals("ONNX_UNAVAILABLE",service.predict().status());
  }

  @Test void springDefaultsSelectEmbeddedOnnxRatherThanPython() {
    var embedded=mock(EmbeddedRegimeService.class);
    var response=NativeRegimeForecast.unavailable("STALE_OR_INCOMPLETE_SESSION");
    when(embedded.predict(20)).thenReturn(response);
    try(var context=new org.springframework.context.annotation.AnnotationConfigApplicationContext()) {
      context.registerBean(ObjectMapper.class,()->new ObjectMapper());
      context.registerBean(EmbeddedRegimeService.class,()->embedded);
      context.registerBean(NativeRegimeService.class);
      context.refresh();
      assertSame(response,context.getBean(NativeRegimeService.class).predict());
      verify(embedded).predict(20);
    }
  }
}
