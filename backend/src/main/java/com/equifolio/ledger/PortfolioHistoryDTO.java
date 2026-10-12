package com.equifolio.ledger;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

public class PortfolioHistoryDTO {

    private String timeframe; // '1W', '1M', '3M', '1Y', 'ALL'
    private BigDecimal currentNav = BigDecimal.ZERO;
    private BigDecimal portfolioReturnPercent = BigDecimal.ZERO;
    private BigDecimal vniReturnPercent = BigDecimal.ZERO;
    private BigDecimal alphaPercent = BigDecimal.ZERO;
    private List<SnapshotPoint> points = new ArrayList<>();

    public static class SnapshotPoint {
        private String date; // 'YYYY-MM-DD' or formatted
        private BigDecimal nav;
        private BigDecimal stockValue;
        private BigDecimal goldValue;
        private BigDecimal savingsValue;
        private BigDecimal cashValue;
        private BigDecimal navReturn; // % change since start of timeframe
        private BigDecimal vniReturn; // % change since start of timeframe
        private BigDecimal vnindex;

        public SnapshotPoint() {}

        public SnapshotPoint(String date, BigDecimal nav, BigDecimal stockValue, BigDecimal goldValue,
                             BigDecimal savingsValue, BigDecimal cashValue, BigDecimal navReturn,
                             BigDecimal vniReturn, BigDecimal vnindex) {
            this.date = date;
            this.nav = nav;
            this.stockValue = stockValue;
            this.goldValue = goldValue;
            this.savingsValue = savingsValue;
            this.cashValue = cashValue;
            this.navReturn = navReturn;
            this.vniReturn = vniReturn;
            this.vnindex = vnindex;
        }

        public String getDate() { return date; }
        public void setDate(String date) { this.date = date; }

        public BigDecimal getNav() { return nav; }
        public void setNav(BigDecimal nav) { this.nav = nav; }

        public BigDecimal getStockValue() { return stockValue; }
        public void setStockValue(BigDecimal stockValue) { this.stockValue = stockValue; }

        public BigDecimal getGoldValue() { return goldValue; }
        public void setGoldValue(BigDecimal goldValue) { this.goldValue = goldValue; }

        public BigDecimal getSavingsValue() { return savingsValue; }
        public void setSavingsValue(BigDecimal savingsValue) { this.savingsValue = savingsValue; }

        public BigDecimal getCashValue() { return cashValue; }
        public void setCashValue(BigDecimal cashValue) { this.cashValue = cashValue; }

        public BigDecimal getNavReturn() { return navReturn; }
        public void setNavReturn(BigDecimal navReturn) { this.navReturn = navReturn; }

        public BigDecimal getVniReturn() { return vniReturn; }
        public void setVniReturn(BigDecimal vniReturn) { this.vniReturn = vniReturn; }

        public BigDecimal getVnindex() { return vnindex; }
        public void setVnindex(BigDecimal vnindex) { this.vnindex = vnindex; }
    }

    public PortfolioHistoryDTO() {}

    public String getTimeframe() { return timeframe; }
    public void setTimeframe(String timeframe) { this.timeframe = timeframe; }

    public BigDecimal getCurrentNav() { return currentNav; }
    public void setCurrentNav(BigDecimal currentNav) { this.currentNav = currentNav; }

    public BigDecimal getPortfolioReturnPercent() { return portfolioReturnPercent; }
    public void setPortfolioReturnPercent(BigDecimal portfolioReturnPercent) { this.portfolioReturnPercent = portfolioReturnPercent; }

    public BigDecimal getVniReturnPercent() { return vniReturnPercent; }
    public void setVniReturnPercent(BigDecimal vniReturnPercent) { this.vniReturnPercent = vniReturnPercent; }

    public BigDecimal getAlphaPercent() { return alphaPercent; }
    public void setAlphaPercent(BigDecimal alphaPercent) { this.alphaPercent = alphaPercent; }

    public List<SnapshotPoint> getPoints() { return points; }
    public void setPoints(List<SnapshotPoint> points) { this.points = points; }
}
