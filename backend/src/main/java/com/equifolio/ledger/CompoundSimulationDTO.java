package com.equifolio.ledger;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

public class CompoundSimulationDTO {

    private BigDecimal initialPrincipal;
    private BigDecimal monthlyContribution;
    private BigDecimal annualRate;
    private int years;

    private BigDecimal totalContributed;
    private BigDecimal totalInterestEarned;
    private BigDecimal futureValue;
    private BigDecimal wealthMultiplier;

    private List<YearlyGrowthItem> yearlyBreakdown = new ArrayList<>();

    public CompoundSimulationDTO() {}

    public static class YearlyGrowthItem {
        private int year;
        private BigDecimal startBalance;
        private BigDecimal yearlyContribution;
        private BigDecimal cumulativeContribution;
        private BigDecimal interestEarnedThisYear;
        private BigDecimal cumulativeInterest;
        private BigDecimal endBalance;

        public YearlyGrowthItem() {}

        public YearlyGrowthItem(int year, BigDecimal startBalance, BigDecimal yearlyContribution,
                                BigDecimal cumulativeContribution, BigDecimal interestEarnedThisYear,
                                BigDecimal cumulativeInterest, BigDecimal endBalance) {
            this.year = year;
            this.startBalance = startBalance;
            this.yearlyContribution = yearlyContribution;
            this.cumulativeContribution = cumulativeContribution;
            this.interestEarnedThisYear = interestEarnedThisYear;
            this.cumulativeInterest = cumulativeInterest;
            this.endBalance = endBalance;
        }

        public int getYear() { return year; }
        public void setYear(int year) { this.year = year; }

        public BigDecimal getStartBalance() { return startBalance; }
        public void setStartBalance(BigDecimal startBalance) { this.startBalance = startBalance; }

        public BigDecimal getYearlyContribution() { return yearlyContribution; }
        public void setYearlyContribution(BigDecimal yearlyContribution) { this.yearlyContribution = yearlyContribution; }

        public BigDecimal getCumulativeContribution() { return cumulativeContribution; }
        public void setCumulativeContribution(BigDecimal cumulativeContribution) { this.cumulativeContribution = cumulativeContribution; }

        public BigDecimal getInterestEarnedThisYear() { return interestEarnedThisYear; }
        public void setInterestEarnedThisYear(BigDecimal interestEarnedThisYear) { this.interestEarnedThisYear = interestEarnedThisYear; }

        public BigDecimal getCumulativeInterest() { return cumulativeInterest; }
        public void setCumulativeInterest(BigDecimal cumulativeInterest) { this.cumulativeInterest = cumulativeInterest; }

        public BigDecimal getEndBalance() { return endBalance; }
        public void setEndBalance(BigDecimal endBalance) { this.endBalance = endBalance; }
    }

    public BigDecimal getInitialPrincipal() { return initialPrincipal; }
    public void setInitialPrincipal(BigDecimal initialPrincipal) { this.initialPrincipal = initialPrincipal; }

    public BigDecimal getMonthlyContribution() { return monthlyContribution; }
    public void setMonthlyContribution(BigDecimal monthlyContribution) { this.monthlyContribution = monthlyContribution; }

    public BigDecimal getAnnualRate() { return annualRate; }
    public void setAnnualRate(BigDecimal annualRate) { this.annualRate = annualRate; }

    public int getYears() { return years; }
    public void setYears(int years) { this.years = years; }

    public BigDecimal getTotalContributed() { return totalContributed; }
    public void setTotalContributed(BigDecimal totalContributed) { this.totalContributed = totalContributed; }

    public BigDecimal getTotalInterestEarned() { return totalInterestEarned; }
    public void setTotalInterestEarned(BigDecimal totalInterestEarned) { this.totalInterestEarned = totalInterestEarned; }

    public BigDecimal getFutureValue() { return futureValue; }
    public void setFutureValue(BigDecimal futureValue) { this.futureValue = futureValue; }

    public BigDecimal getWealthMultiplier() { return wealthMultiplier; }
    public void setWealthMultiplier(BigDecimal wealthMultiplier) { this.wealthMultiplier = wealthMultiplier; }

    public List<YearlyGrowthItem> getYearlyBreakdown() { return yearlyBreakdown; }
    public void setYearlyBreakdown(List<YearlyGrowthItem> yearlyBreakdown) { this.yearlyBreakdown = yearlyBreakdown; }
}
