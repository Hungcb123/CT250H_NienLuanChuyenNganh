package com.equifolio.ledger;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class PortfolioValuationDTO {
    private BigDecimal totalNetWorth = BigDecimal.ZERO;
    private BigDecimal cashBalance = BigDecimal.ZERO;
    private BigDecimal stockValue = BigDecimal.ZERO;
    private BigDecimal goldValue = BigDecimal.ZERO;
    private BigDecimal savingsValue = BigDecimal.ZERO;

    private Map<String, BigDecimal> currentAllocations = new HashMap<>(); // 'STOCK', 'GOLD', 'CASH_SAVINGS'
    private List<HoldingItem> holdings = new ArrayList<>();

    public static class HoldingItem {
        private String accountCode;
        private String ticker;
        private String assetName;
        private String assetClass;
        private BigDecimal quantity;
        private BigDecimal currentPrice;
        private BigDecimal marketValue;
        private BigDecimal allocationPercent;

        public HoldingItem() {}

        public HoldingItem(String accountCode, String ticker, String assetName, String assetClass,
                           BigDecimal quantity, BigDecimal currentPrice, BigDecimal marketValue, BigDecimal allocationPercent) {
            this.accountCode = accountCode;
            this.ticker = ticker;
            this.assetName = assetName;
            this.assetClass = assetClass;
            this.quantity = quantity;
            this.currentPrice = currentPrice;
            this.marketValue = marketValue;
            this.allocationPercent = allocationPercent;
        }

        public String getAccountCode() { return accountCode; }
        public void setAccountCode(String accountCode) { this.accountCode = accountCode; }

        public String getTicker() { return ticker; }
        public void setTicker(String ticker) { this.ticker = ticker; }

        public String getAssetName() { return assetName; }
        public void setAssetName(String assetName) { this.assetName = assetName; }

        public String getAssetClass() { return assetClass; }
        public void setAssetClass(String assetClass) { this.assetClass = assetClass; }

        public BigDecimal getQuantity() { return quantity; }
        public void setQuantity(BigDecimal quantity) { this.quantity = quantity; }

        public BigDecimal getCurrentPrice() { return currentPrice; }
        public void setCurrentPrice(BigDecimal currentPrice) { this.currentPrice = currentPrice; }

        public BigDecimal getMarketValue() { return marketValue; }
        public void setMarketValue(BigDecimal marketValue) { this.marketValue = marketValue; }

        public BigDecimal getAllocationPercent() { return allocationPercent; }
        public void setAllocationPercent(BigDecimal allocationPercent) { this.allocationPercent = allocationPercent; }
    }

    public PortfolioValuationDTO() {}

    public BigDecimal getTotalNetWorth() { return totalNetWorth; }
    public void setTotalNetWorth(BigDecimal totalNetWorth) { this.totalNetWorth = totalNetWorth; }

    public BigDecimal getCashBalance() { return cashBalance; }
    public void setCashBalance(BigDecimal cashBalance) { this.cashBalance = cashBalance; }

    public BigDecimal getStockValue() { return stockValue; }
    public void setStockValue(BigDecimal stockValue) { this.stockValue = stockValue; }

    public BigDecimal getGoldValue() { return goldValue; }
    public void setGoldValue(BigDecimal goldValue) { this.goldValue = goldValue; }

    public BigDecimal getSavingsValue() { return savingsValue; }
    public void setSavingsValue(BigDecimal savingsValue) { this.savingsValue = savingsValue; }

    public Map<String, BigDecimal> getCurrentAllocations() { return currentAllocations; }
    public void setCurrentAllocations(Map<String, BigDecimal> currentAllocations) { this.currentAllocations = currentAllocations; }

    public List<HoldingItem> getHoldings() { return holdings; }
    public void setHoldings(List<HoldingItem> holdings) { this.holdings = holdings; }
}
