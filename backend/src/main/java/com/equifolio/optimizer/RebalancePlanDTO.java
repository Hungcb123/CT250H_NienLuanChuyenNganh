package com.equifolio.optimizer;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class RebalancePlanDTO {
    private boolean driftDetected;
    private BigDecimal maxDriftPercent;
    private Map<String, BigDecimal> currentAllocations = new HashMap<>();
    private Map<String, BigDecimal> targetAllocations = new HashMap<>();
    private List<RebalanceAction> actions = new ArrayList<>();
    private String executiveSummary;

    public static class RebalanceAction {
        private String actionType; // 'BUY', 'SELL', 'HOLD'
        private String ticker;
        private String assetName;
        private String assetClass;
        private BigDecimal exactQuantity;
        private BigDecimal roundedQuantity; // Lô chẵn 100 cp hoặc số chỉ vàng nguyên
        private BigDecimal estimatedPrice;
        private BigDecimal estimatedTotalMoney;
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

    public List<RebalanceAction> getActions() { return actions; }
    public void setActions(List<RebalanceAction> actions) { this.actions = actions; }

    public String getExecutiveSummary() { return executiveSummary; }
    public void setExecutiveSummary(String executiveSummary) { this.executiveSummary = executiveSummary; }
}
