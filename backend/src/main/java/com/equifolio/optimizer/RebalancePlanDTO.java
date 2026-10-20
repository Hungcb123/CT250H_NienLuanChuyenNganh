package com.equifolio.optimizer;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class RebalancePlanDTO {
    private int horizonSessions = 20;
    public int getHorizonSessions() { return horizonSessions; }
    public void setHorizonSessions(int value) { horizonSessions = value; }
    private EquityPreferenceService.Preference equityPreference;
    public EquityPreferenceService.Preference getEquityPreference() { return equityPreference; }
    public void setEquityPreference(EquityPreferenceService.Preference value) { equityPreference=value; }
    private String equityNotice;
    public String getEquityNotice() { return equityNotice; }
    public void setEquityNotice(String value) { equityNotice=value; }
    private String planToken;
    public String getPlanToken() { return planToken; }
    public void setPlanToken(String value) { this.planToken = value; }
    private boolean taaEnabled;
    public boolean isTaaEnabled() { return taaEnabled; }
    public void setTaaEnabled(boolean enabled) { this.taaEnabled = enabled; }
    private boolean driftDetected;
    private BigDecimal maxDriftPercent = BigDecimal.ZERO;
    private Map<String, BigDecimal> currentAllocations = new HashMap<>();
    private Map<String, BigDecimal> targetAllocations = new HashMap<>();

    // ── TAA fields mới ──
    private Map<String, BigDecimal> saaTargets = new HashMap<>();       // Tỷ trọng mỏ neo SAA (từ khảo sát)
    private Map<String, BigDecimal> taaTargets = new HashMap<>();       // Tỷ trọng sau ML adjust
    private List<MlPredictionInfo> mlPredictions = new ArrayList<>();   // Chi tiết dự báo ML

    private List<RebalanceAction> actions = new ArrayList<>();
    private String executiveSummary;
    private BigDecimal totalEstimatedSell = BigDecimal.ZERO;
    private BigDecimal totalEstimatedBuy = BigDecimal.ZERO;
    private BigDecimal totalEstimatedFees = BigDecimal.ZERO;
    private BigDecimal totalEstimatedTax = BigDecimal.ZERO;
    private BigDecimal netCashImpact = BigDecimal.ZERO;

    /**
     * Thông tin dự báo ML cho một lớp tài sản.
     */
    public static class MlPredictionInfo {
        private int horizonSessions = 20;
        public int getHorizonSessions() { return horizonSessions; }
        public void setHorizonSessions(int value) { horizonSessions = value; }
        private String assetClass;    // "STOCK" hoặc "GOLD"
        private String modelName;     // "stock_regime.onnx" hoặc "gold_trend.onnx"
        private int signal;           // -1, 0, +1
        private double confidence;    // 0.0 → 1.0
        private String regimeName;    // "BULLISH_UPTREND", etc.
        private BigDecimal deltaWeight; // Δw = Signal × P × 15%
        private String scoreSemantics;
        private NativeRegimeForecast nativeForecast;

        public String getScoreSemantics() { return scoreSemantics; }
        public NativeRegimeForecast getNativeForecast() { return nativeForecast; }
        public void setNativeForecast(NativeRegimeForecast forecast) {
            this.nativeForecast = forecast;
            this.scoreSemantics = "class_balanced_decision_scores_not_probabilities";
        }

        public MlPredictionInfo() {}

        public MlPredictionInfo(String assetClass, String modelName, int signal,
                                double confidence, String regimeName, BigDecimal deltaWeight) {
            this.assetClass = assetClass;
            this.modelName = modelName;
            this.signal = signal;
            this.confidence = confidence;
            this.regimeName = regimeName;
            this.deltaWeight = deltaWeight;
        }

        public String getAssetClass() { return assetClass; }
        public void setAssetClass(String assetClass) { this.assetClass = assetClass; }

        public String getModelName() { return modelName; }
        public void setModelName(String modelName) { this.modelName = modelName; }

        public int getSignal() { return signal; }
        public void setSignal(int signal) { this.signal = signal; }

        public double getConfidence() { return confidence; }
        public void setConfidence(double confidence) { this.confidence = confidence; }

        public String getRegimeName() { return regimeName; }
        public void setRegimeName(String regimeName) { this.regimeName = regimeName; }

        public BigDecimal getDeltaWeight() { return deltaWeight; }
        public void setDeltaWeight(BigDecimal deltaWeight) { this.deltaWeight = deltaWeight; }
    }

    public static class RebalanceAction {
        private boolean earlySettlement;
        public boolean isEarlySettlement() { return earlySettlement; }
        public void setEarlySettlement(boolean value) { this.earlySettlement = value; }
        private String actionType; // 'BUY', 'SELL', 'HOLD'
        private String ticker;
        private String assetName;
        private int horizonSessions = 20;
        public int getHorizonSessions() { return horizonSessions; }
        public void setHorizonSessions(int value) { horizonSessions = value; }
        private String assetClass;
        private BigDecimal exactQuantity;
        private BigDecimal roundedQuantity; // Lô chẵn 100 cp hoặc số chỉ vàng nguyên
        private BigDecimal estimatedPrice;
        private BigDecimal estimatedTotalMoney;
        private BigDecimal estimatedFee = BigDecimal.ZERO;
        private BigDecimal estimatedTax = BigDecimal.ZERO;
        private BigDecimal netMoney = BigDecimal.ZERO;
        private String note;

        public RebalanceAction() {}

        public RebalanceAction(String actionType, String ticker, String assetName, String assetClass,
                               BigDecimal exactQuantity, BigDecimal roundedQuantity, BigDecimal estimatedPrice,
                               BigDecimal estimatedTotalMoney, String note) {
            this.actionType = actionType;
            this.ticker = ticker;
            this.assetName = assetName;
            this.assetClass = assetClass;
            this.exactQuantity = exactQuantity;
            this.roundedQuantity = roundedQuantity;
            this.estimatedPrice = estimatedPrice;
            this.estimatedTotalMoney = estimatedTotalMoney;
            this.note = note;
        }

        public String getActionType() { return actionType; }
        public void setActionType(String actionType) { this.actionType = actionType; }

        public String getTicker() { return ticker; }
        public void setTicker(String ticker) { this.ticker = ticker; }

        public String getAssetName() { return assetName; }
        public void setAssetName(String assetName) { this.assetName = assetName; }

        public String getAssetClass() { return assetClass; }
        public void setAssetClass(String assetClass) { this.assetClass = assetClass; }

        public BigDecimal getExactQuantity() { return exactQuantity; }
        public void setExactQuantity(BigDecimal exactQuantity) { this.exactQuantity = exactQuantity; }

        public BigDecimal getRoundedQuantity() { return roundedQuantity; }
        public void setRoundedQuantity(BigDecimal roundedQuantity) { this.roundedQuantity = roundedQuantity; }

        public BigDecimal getEstimatedPrice() { return estimatedPrice; }
        public void setEstimatedPrice(BigDecimal estimatedPrice) { this.estimatedPrice = estimatedPrice; }

        public BigDecimal getEstimatedTotalMoney() { return estimatedTotalMoney; }
        public void setEstimatedTotalMoney(BigDecimal estimatedTotalMoney) { this.estimatedTotalMoney = estimatedTotalMoney; }

        public BigDecimal getEstimatedFee() { return estimatedFee; }
        public void setEstimatedFee(BigDecimal estimatedFee) { this.estimatedFee = estimatedFee; }

        public BigDecimal getEstimatedTax() { return estimatedTax; }
        public void setEstimatedTax(BigDecimal estimatedTax) { this.estimatedTax = estimatedTax; }

        public BigDecimal getNetMoney() { return netMoney; }
        public void setNetMoney(BigDecimal netMoney) { this.netMoney = netMoney; }

        public String getNote() { return note; }
        public void setNote(String note) { this.note = note; }
    }

    public RebalancePlanDTO() {}

    public boolean isDriftDetected() { return driftDetected; }
    public void setDriftDetected(boolean driftDetected) { this.driftDetected = driftDetected; }

    public BigDecimal getMaxDriftPercent() { return maxDriftPercent; }
    public void setMaxDriftPercent(BigDecimal maxDriftPercent) { this.maxDriftPercent = maxDriftPercent; }

    public Map<String, BigDecimal> getCurrentAllocations() { return currentAllocations; }
    public void setCurrentAllocations(Map<String, BigDecimal> currentAllocations) { this.currentAllocations = currentAllocations; }

    public Map<String, BigDecimal> getTargetAllocations() { return targetAllocations; }
    public void setTargetAllocations(Map<String, BigDecimal> targetAllocations) { this.targetAllocations = targetAllocations; }

    public Map<String, BigDecimal> getSaaTargets() { return saaTargets; }
    public void setSaaTargets(Map<String, BigDecimal> saaTargets) { this.saaTargets = saaTargets; }

    public Map<String, BigDecimal> getTaaTargets() { return taaTargets; }
    public void setTaaTargets(Map<String, BigDecimal> taaTargets) { this.taaTargets = taaTargets; }

    public List<MlPredictionInfo> getMlPredictions() { return mlPredictions; }
    public void setMlPredictions(List<MlPredictionInfo> mlPredictions) { this.mlPredictions = mlPredictions; }

    public List<RebalanceAction> getActions() { return actions; }
    public void setActions(List<RebalanceAction> actions) { this.actions = actions; }

    public String getExecutiveSummary() { return executiveSummary; }
    public void setExecutiveSummary(String executiveSummary) { this.executiveSummary = executiveSummary; }

    public BigDecimal getTotalEstimatedSell() { return totalEstimatedSell; }
    public void setTotalEstimatedSell(BigDecimal totalEstimatedSell) { this.totalEstimatedSell = totalEstimatedSell; }

    public BigDecimal getTotalEstimatedBuy() { return totalEstimatedBuy; }
    public void setTotalEstimatedBuy(BigDecimal totalEstimatedBuy) { this.totalEstimatedBuy = totalEstimatedBuy; }

    public BigDecimal getTotalEstimatedFees() { return totalEstimatedFees; }
    public void setTotalEstimatedFees(BigDecimal totalEstimatedFees) { this.totalEstimatedFees = totalEstimatedFees; }

    public BigDecimal getTotalEstimatedTax() { return totalEstimatedTax; }
    public void setTotalEstimatedTax(BigDecimal totalEstimatedTax) { this.totalEstimatedTax = totalEstimatedTax; }

    public BigDecimal getNetCashImpact() { return netCashImpact; }
    public void setNetCashImpact(BigDecimal netCashImpact) { this.netCashImpact = netCashImpact; }
}
