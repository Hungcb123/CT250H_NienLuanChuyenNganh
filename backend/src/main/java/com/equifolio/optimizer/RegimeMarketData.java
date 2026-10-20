package com.equifolio.optimizer;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.http.*;
import java.time.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/** Immutable reviewed prefix plus append-only completed DNSE bars in PostgreSQL. */
@Service
public class RegimeMarketData {
  public record Snapshot(List<ShockFeatures.Bar> index,List<ShockFeatures.Bar> etf) {}
  public static final ZoneId ZONE=ZoneId.of("Asia/Ho_Chi_Minh");
  private final JdbcTemplate jdbc;
  private final TransactionTemplate transactions;
  private final ObjectMapper mapper;
  private final Map<String,List<ShockFeatures.Bar>> seed=new HashMap<>();
  private final HttpClient http=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(6)).build();

  public RegimeMarketData(ShockOnnxModel model,JdbcTemplate jdbc,TransactionTemplate transactions,ObjectMapper mapper) {
    this.jdbc=jdbc;this.transactions=transactions;this.mapper=mapper;
    try {
      var data=mapper.readTree(model.read("market_seed.json"));
      seed.put("VNINDEX",readBars(data.get("index")));seed.put("E1VFVN30",readBars(data.get("etf")));
    }catch(Exception e){throw new IllegalStateException("Cannot load ONNX market seed",e);}
  }
  static List<ShockFeatures.Bar> readBars(JsonNode rows) {
    var result=new ArrayList<ShockFeatures.Bar>();
    for(var row:rows)result.add(new ShockFeatures.Bar(LocalDate.parse(row.path("date").asText()),
        number(row,"close"),number(row,"open"),number(row,"high"),number(row,"low"),number(row,"volume")));
    return List.copyOf(result);
  }
  private static double number(JsonNode row,String key){return row.path(key).isNumber()?row.get(key).doubleValue():Double.NaN;}
  public static LocalDate completedSession(ZonedDateTime now) {
    now=now.withZoneSameInstant(ZONE);
    LocalDate day=now.toLocalDate();
    if(now.toLocalTime().isBefore(LocalTime.of(15,30)))day=day.minusDays(1);
    while(day.getDayOfWeek()==DayOfWeek.SATURDAY||day.getDayOfWeek()==DayOfWeek.SUNDAY)day=day.minusDays(1);
    return day;
  }
  private List<ShockFeatures.Bar> load(String ticker) {
    var rows=new ArrayList<>(seed.get(ticker));
    rows.addAll(jdbc.query("SELECT * FROM ml_onnx_market_bars WHERE ticker=? AND session_date>? ORDER BY session_date",
        (rs,n)->new ShockFeatures.Bar(rs.getDate("session_date").toLocalDate(),rs.getDouble("close"),
            rs.getDouble("open"),rs.getDouble("high"),rs.getDouble("low"),rs.getDouble("volume")),
        ticker,rows.getLast().date()));
    return List.copyOf(rows);
  }
  public Snapshot snapshot(){return new Snapshot(load("VNINDEX"),load("E1VFVN30"));}

  public synchronized void sync(LocalDate expected) throws Exception {
    var snapshot=snapshot();
    if(snapshot.index().getLast().date().equals(expected)&&snapshot.etf().getLast().date().equals(expected))return;
    var incoming=new HashMap<String,List<ShockFeatures.Bar>>();
    var hashes=new HashMap<String,String>();
    for(String ticker:List.of("VNINDEX","E1VFVN30")) {
      var history=ticker.equals("VNINDEX")?snapshot.index():snapshot.etf();
      // Check overlap only for previously ingested DNSE suffixes; the seed is
      // a separately reviewed source and must not be revised by live quotes.
      LocalDate last=history.getLast().date(),seedEnd=seed.get(ticker).getLast().date();
      LocalDate begin=last.isAfter(seedEnd)?last:last.plusDays(1);
      if(begin.isAfter(expected)){incoming.put(ticker,List.of());continue;}
      var fetched=new ArrayList<ShockFeatures.Bar>();
      var receipts=new StringBuilder();
      while(!begin.isAfter(expected)) {
        var end=begin.plusDays(89).isBefore(expected)?begin.plusDays(89):expected;
        String kind=ticker.equals("VNINDEX")?"index":"stock";
        String url="https://services.entrade.com.vn/chart-api/v2/ohlcs/"+kind+"?symbol="+ticker
            +"&resolution=1D&from="+begin.atStartOfDay(ZONE).toEpochSecond()+"&to="+end.plusDays(1).atStartOfDay(ZONE).toEpochSecond();
        var request=HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(20))
            .header("User-Agent","Mozilla/5.0 EquiFolio/1.0").GET().build();
        var response=http.send(request,HttpResponse.BodyHandlers.ofByteArray());
        if(response.statusCode()!=200)throw new IllegalArgumentException("MARKET_SOURCE_UNAVAILABLE");
        fetched.addAll(parseDnse(mapper.readTree(response.body()),ticker,begin,end));
        receipts.append(ShockOnnxModel.hash(response.body()));begin=end.plusDays(1);
      }
      if(fetched.isEmpty()||!fetched.getLast().date().equals(expected))throw new IllegalArgumentException("STALE_OR_INCOMPLETE_SESSION");
      incoming.put(ticker,List.copyOf(fetched));
      hashes.put(ticker,ShockOnnxModel.hash(receipts.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)));
    }
    var indexDates=new TreeSet<LocalDate>();snapshot.index().forEach(b->indexDates.add(b.date()));
    incoming.get("VNINDEX").forEach(b->indexDates.add(b.date()));
    var etfDates=new TreeSet<LocalDate>();snapshot.etf().forEach(b->etfDates.add(b.date()));
    incoming.get("E1VFVN30").forEach(b->etfDates.add(b.date()));
    for(var date:indexDates.tailSet(seed.get("VNINDEX").getLast().date(),false))
      if(!etfDates.contains(date))throw new IllegalArgumentException("ETF_SESSION_MISSING");
    transactions.executeWithoutResult(status->{
      jdbc.execute("SELECT pg_advisory_xact_lock(734925)");
      for(String ticker:List.of("VNINDEX","E1VFVN30")) {
        var stored=new HashMap<LocalDate,ShockFeatures.Bar>();load(ticker).forEach(b->stored.put(b.date(),b));
        for(var b:incoming.get(ticker)) {
          var old=stored.get(b.date());
          if(old!=null) {
            if(Math.abs(old.close()-b.close())>.011||Math.abs(old.open()-b.open())>.011
                ||Math.abs(old.high()-b.high())>.011||Math.abs(old.low()-b.low())>.011||Math.abs(old.volume()-b.volume())>.011)
              throw new IllegalArgumentException("HISTORICAL_REVISION");
          }else jdbc.update("INSERT INTO ml_onnx_market_bars(ticker,session_date,close,open,high,low,volume,source_sha256) VALUES (?,?,?,?,?,?,?,?)",
              ticker,b.date(),b.close(),b.open(),b.high(),b.low(),b.volume(),hashes.get(ticker));
        }
      }
    });
  }

  static List<ShockFeatures.Bar> parseDnse(JsonNode json,String ticker,LocalDate start,LocalDate end) {
    int size=json.path("t").size();
    if(size==0||!json.path("t").isArray())throw new IllegalArgumentException("INVALID_DNSE_RESPONSE");
    for(String key:List.of("o","h","l","c","v"))
      if(!json.path(key).isArray()||json.get(key).size()!=size)throw new IllegalArgumentException("INVALID_DNSE_RESPONSE");
    var result=new ArrayList<ShockFeatures.Bar>();
    double factor=ticker.equals("E1VFVN30")?1000:1;
    for(int i=0;i<size;i++) {
      for(String key:List.of("t","o","h","l","c","v"))if(!json.get(key).get(i).isNumber())throw new IllegalArgumentException("INVALID_DNSE_RESPONSE");
      var date=Instant.ofEpochSecond(json.get("t").get(i).asLong()).atZone(ZONE).toLocalDate();
      if(date.isBefore(start)||date.isAfter(end))continue;
      double o=json.get("o").get(i).doubleValue()*factor,h=json.get("h").get(i).doubleValue()*factor,
          l=json.get("l").get(i).doubleValue()*factor,c=json.get("c").get(i).doubleValue()*factor,v=json.get("v").get(i).doubleValue();
      if(!Double.isFinite(o+h+l+c+v)||Math.min(Math.min(o,h),Math.min(l,c))<=0||v<0
          ||h<Math.max(o,c)||l>Math.min(o,c)||h<l||date.getDayOfWeek().getValue()>5
          ||(!result.isEmpty()&&!date.isAfter(result.getLast().date())))throw new IllegalArgumentException("INVALID_DNSE_VALUES");
      result.add(new ShockFeatures.Bar(date,c,o,h,l,v));
    }
    return List.copyOf(result);
  }
}
