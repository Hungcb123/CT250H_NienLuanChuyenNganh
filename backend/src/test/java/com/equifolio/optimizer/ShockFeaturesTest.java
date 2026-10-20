package com.equifolio.optimizer;

import static org.junit.jupiter.api.Assertions.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class ShockFeaturesTest {
  private final ObjectMapper mapper=new ObjectMapper();
  @Test void allRawFeatureRowsMatchFrozenPython() throws Exception {
    var seed=mapper.readTree(getClass().getResourceAsStream("/models/shock/market_seed.json"));
    var index=RegimeMarketData.readBars(seed.get("index"));
    var etf=RegimeMarketData.readBars(seed.get("etf"));
    var contract=mapper.readTree(getClass().getResourceAsStream("/models/shock/contract.json"));
    var names=new ArrayList<String>();contract.get("features").forEach(n->names.add(n.asText()));
    var positions=new HashMap<String,Integer>();for(int i=0;i<index.size();i++)positions.put(index.get(i).date().toString(),i);
    var cases=mapper.readTree(getClass().getResourceAsStream("/models/shock_feature_cases.json"));
    assertTrue(cases.size()>1500);
    for(var row:cases) {
      String date=row.get("session").asText();
      var actual=ShockFeatures.calculate(index.subList(0,positions.get(date)+1),etf,names);
      assertEquals(row.get("sigma").asDouble(),actual.sigma(),1e-12,date);
      for(int j=0;j<names.size();j++)assertEquals(row.get("features").get(j).asDouble(),actual.features()[j],
          j<12?2e-5:1e-8,date+" "+names.get(j));
    }
  }
  @Test void completionUsesMarketTimezoneCloseAndWeekends() {
    var zone=RegimeMarketData.ZONE;
    assertEquals(LocalDate.parse("2026-10-16"),RegimeMarketData.completedSession(ZonedDateTime.of(2026,10,19,15,29,0,0,zone)));
    assertEquals(LocalDate.parse("2026-10-19"),RegimeMarketData.completedSession(ZonedDateTime.of(2026,10,19,15,30,0,0,zone)));
    assertEquals(LocalDate.parse("2026-10-16"),RegimeMarketData.completedSession(ZonedDateTime.of(2026,10,18,20,0,0,0,zone)));
  }
  @Test void malformedOrReorderedDnseDataCannotEnterFeatures() throws Exception {
    long date=LocalDate.parse("2026-10-19").atStartOfDay(RegimeMarketData.ZONE).toEpochSecond();
    var payload=mapper.readTree("{\"t\":["+date+"],\"o\":[20],\"h\":[22],\"l\":[19],\"c\":[21],\"v\":[100]}");
    var day=LocalDate.parse("2026-10-19");
    var bars=RegimeMarketData.parseDnse(payload,"E1VFVN30",day,day);
    assertEquals(21000,bars.getFirst().close());
    ((com.fasterxml.jackson.databind.node.ArrayNode)payload.get("h")).set(0,mapper.getNodeFactory().numberNode(18));
    assertThrows(IllegalArgumentException.class,()->RegimeMarketData.parseDnse(payload,"VNINDEX",day,day));
  }
}
