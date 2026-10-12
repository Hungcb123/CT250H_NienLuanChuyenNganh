package com.equifolio.optimizer;

import com.equifolio.ledger.PortfolioValuationDTO;
import java.math.BigDecimal;

public class RebalanceExecutionResultDTO {
    private String transactionCode;
    private int actionCount;
    private BigDecimal totalSoldMoney = BigDecimal.ZERO;
    private BigDecimal totalBoughtMoney = BigDecimal.ZERO;
    private BigDecimal netCashChange = BigDecimal.ZERO;
    private PortfolioValuationDTO updatedValuation;
    private RebalancePlanDTO updatedPlan;
    private String message;

    public RebalanceExecutionResultDTO() {}

    public String getTransactionCode() { return transactionCode; }
    public void setTransactionCode(String transactionCode) { this.transactionCode = transactionCode; }

    public int getActionCount() { return actionCount; }
    public void setActionCount(int actionCount) { this.actionCount = actionCount; }

    public BigDecimal getTotalSoldMoney() { return totalSoldMoney; }
    public void setTotalSoldMoney(BigDecimal totalSoldMoney) { this.totalSoldMoney = totalSoldMoney; }

    public BigDecimal getTotalBoughtMoney() { return totalBoughtMoney; }
    public void setTotalBoughtMoney(BigDecimal totalBoughtMoney) { this.totalBoughtMoney = totalBoughtMoney; }

    public BigDecimal getNetCashChange() { return netCashChange; }
    public void setNetCashChange(BigDecimal netCashChange) { this.netCashChange = netCashChange; }

    public PortfolioValuationDTO getUpdatedValuation() { return updatedValuation; }
    public void setUpdatedValuation(PortfolioValuationDTO updatedValuation) { this.updatedValuation = updatedValuation; }

    public RebalancePlanDTO getUpdatedPlan() { return updatedPlan; }
    public void setUpdatedPlan(RebalancePlanDTO updatedPlan) { this.updatedPlan = updatedPlan; }

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
}
