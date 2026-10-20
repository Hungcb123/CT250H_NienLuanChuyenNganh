package com.equifolio.optimizer;

import java.time.LocalDate;
import java.util.*;

/** Completed-session features matching the frozen Python research formulas. */
public final class ShockFeatures {
  public record Bar(LocalDate date, double close, double open, double high, double low, double volume) {}
  public record Input(LocalDate session, LocalDate previousSession, double[] features, double sigma) {}
  private ShockFeatures() {}

  public static Input calculate(List<Bar> index, List<Bar> etf, List<String> names) {
    int n = index.size(), t = n - 1;
    if (n < 252) throw new IllegalArgumentException("INSUFFICIENT_HISTORY");
    double[] p = new double[n], r = new double[n], e = new double[n], er = new double[n];
    var byDate = new HashMap<LocalDate, Bar>();
    for (var b : etf) byDate.put(b.date(), b);
    Arrays.fill(r, Double.NaN); Arrays.fill(er, Double.NaN);
    for (int i = 0; i < n; i++) {
      var b = index.get(i);
      if (!Double.isFinite(b.close()) || b.close() <= 0 || (i > 0 && !b.date().isAfter(index.get(i-1).date())))
        throw new IllegalArgumentException("INVALID_MARKET_DATA");
      p[i] = b.close();
      var eb = byDate.get(b.date());
      e[i] = eb == null || eb.volume() <= 0 ? Double.NaN : eb.close();
      if (i > 0) { r[i] = Math.log(p[i])-Math.log(p[i-1]); er[i] = Math.log(e[i])-Math.log(e[i-1]); }
    }
    var f = new HashMap<String, Double>();
    var close = CloseFeatures.calculate(p);
    var core = CloseFeatures.NAMES.split(",");
    for (int i=0; i<core.length; i++) f.put(core[i], (double)close[i]);
    double vol20 = std(r, t, 20), vol60 = std(r, t, 60), sigma = vol20 * Math.sqrt(20);
    if (!Double.isFinite(sigma) || sigma <= 0) throw new IllegalArgumentException("INVALID_MODEL_INPUT");
    double roc = e[t]/e[t-20]-1;
    for(int i=t-20;i<=t;i++) if(!Double.isFinite(e[i])) roc=Double.NaN;
    f.put("ETF_ROC20", roc*100);
    f.put("ETF_HV20", std(er,t,20)*Math.sqrt(252)*100);
    f.put("ETF_ReturnSpread20", (roc-(p[t]/p[t-20]-1))*100);
    double mr=mean(r,t,30), me=mean(er,t,30), covariance=0;
    for(int i=t-29;i<=t;i++) covariance+=(r[i]-mr)*(er[i]-me);
    f.put("ETF_Corr30_VNINDEX", covariance/29/std(r,t,30)/std(er,t,30));
    f.put("ROC60", (p[t]/p[t-60]-1)*100);
    f.put("ROC120", (p[t]/p[t-120]-1)*100);
    f.put("DistSMA200", (p[t]/mean(p,t,200)-1)*100);
    f.put("Drawdown120", (p[t]/max(p,t,120)-1)*100);
    f.put("Drawdown252", (p[t]/max(p,t,252)-1)*100);
    f.put("HV20_60_Ratio", vol20/vol60);
    double downside60=0;
    for(int i=t-59;i<=t;i++) downside60+=Math.pow(Math.min(r[i],0),2);
    f.put("DownsideHV60", Math.sqrt(downside60/60)*Math.sqrt(252)*100);
    var bar=index.get(t);
    double spread=bar.high()>bar.low() ? bar.high()-bar.low() : Double.NaN;
    double range=spread/p[t]/vol20;
    double[] volumes=index.subList(n-60,n).stream().mapToDouble(Bar::volume).filter(Double::isFinite).sorted().toArray();
    double median=volumes.length<30 ? Double.NaN : (volumes[(volumes.length-1)/2]+volumes[volumes.length/2])/2;
    double volumeLog=Math.log(bar.volume()/median);
    f.put("IntradayRangeSigma", range);
    f.put("CloseLocation", Math.max(0,Math.min(1,(p[t]-bar.low())/spread)));
    f.put("UpperWickSigma", Math.max(0,(bar.high()-Math.max(bar.open(),p[t]))/p[t]/vol20));
    f.put("BodySigma", (p[t]-bar.open())/p[t]/vol20);
    f.put("VolumeLogRatio60", volumeLog);
    f.put("RangeVolumeInteraction", range*volumeLog);
    for(int h:new int[]{3,5,10,20,60}) f.put("momentum_z"+h,Math.log(p[t]/p[t-h])/vol20/Math.sqrt(h));
    for(int lag=0;lag<=2;lag++) f.put(lag==0?"shock_now":"shock_lag"+lag,r[t-lag]/std(r,t-lag-1,20));
    double down=0,energy=0; int negative5=0,negative20=0;
    for(int i=t-19;i<=t;i++) { energy+=r[i]*r[i]; if(r[i]<0) {down+=r[i]*r[i];negative20++;if(i>=t-4)negative5++;} }
    f.put("downside_energy_share20",down/energy);
    f.put("negative_share5",negative5/5.);
    f.put("negative_share20",negative20/20.);
    f.put("volatility5_20",std(r,t,5)/vol20);
    f.put("drawdown_z20",Math.log(p[t]/max(p,t,20))/vol20/Math.sqrt(20));
    f.put("drawdown_z60",Math.log(p[t]/max(p,t,60))/vol20/Math.sqrt(60));
    double m=mean(r,t,20), third=0;
    for(int i=t-19;i<=t;i++) third+=Math.pow((r[i]-m)/vol20,3);
    f.put("skew20",20./19/18*third);
    f.put("momentum_acceleration",f.get("momentum_z5")-f.get("momentum_z20"));
    double[] values=new double[names.size()];
    for(int i=0;i<values.length;i++) {
      var value=f.get(names.get(i));
      if(value==null || !Double.isFinite(value)) throw new IllegalArgumentException("INVALID_MODEL_INPUT");
      values[i]=value;
    }
    return new Input(bar.date(),index.get(t-1).date(),values,sigma);
  }

  private static double mean(double[] a,int end,int count) {
    double sum=0; for(int i=end-count+1;i<=end;i++)sum+=a[i]; return sum/count;
  }
  private static double std(double[] a,int end,int count) {
    double m=mean(a,end,count),sum=0; for(int i=end-count+1;i<=end;i++)sum+=Math.pow(a[i]-m,2);
    return Math.sqrt(sum/(count-1));
  }
  private static double max(double[] a,int end,int count) {
    double value=Double.NEGATIVE_INFINITY; for(int i=end-count+1;i<=end;i++)value=Math.max(value,a[i]); return value;
  }
}
