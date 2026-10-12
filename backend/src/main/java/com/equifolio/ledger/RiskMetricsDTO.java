package com.equifolio.ledger;

import java.math.BigDecimal;

public class RiskMetricsDTO {

    private BigDecimal sharpeRatio = BigDecimal.ZERO;
    private BigDecimal maxDrawdownPercent = BigDecimal.ZERO;
    private BigDecimal annualizedVolatilityPercent = BigDecimal.ZERO;
    private BigDecimal annualizedReturnPercent = BigDecimal.ZERO;
    private BigDecimal riskFreeRatePercent = new BigDecimal("5.0");
    private BigDecimal alphaPercent = BigDecimal.ZERO;
    private BigDecimal beta = BigDecimal.ONE;
    private String riskRating = "MODERATE";
    private String interpretation;

    public RiskMetricsDTO() {}

    public BigDecimal getSharpeRatio() { return sharpeRatio; }
    public void setSharpeRatio(BigDecimal sharpeRatio) { this.sharpeRatio = sharpeRatio; }

    public BigDecimal getMaxDrawdownPercent() { return maxDrawdownPercent; }
    public void setMaxDrawdownPercent(BigDecimal maxDrawdownPercent) { this.maxDrawdownPercent = maxDrawdownPercent; }

    public BigDecimal getAnnualizedVolatilityPercent() { return annualizedVolatilityPercent; }
    public void setAnnualizedVolatilityPercent(BigDecimal annualizedVolatilityPercent) { this.annualizedVolatilityPercent = annualizedVolatilityPercent; }

    public BigDecimal getAnnualizedReturnPercent() { return annualizedReturnPercent; }
    public void setAnnualizedReturnPercent(BigDecimal annualizedReturnPercent) { this.annualizedReturnPercent = annualizedReturnPercent; }

    public BigDecimal getRiskFreeRatePercent() { return riskFreeRatePercent; }
    public void setRiskFreeRatePercent(BigDecimal riskFreeRatePercent) { this.riskFreeRatePercent = riskFreeRatePercent; }

    public BigDecimal getAlphaPercent() { return alphaPercent; }
    public void setAlphaPercent(BigDecimal alphaPercent) { this.alphaPercent = alphaPercent; }

    public BigDecimal getBeta() { return beta; }
    public void setBeta(BigDecimal beta) { this.beta = beta; }

    public String getRiskRating() { return riskRating; }
    public void setRiskRating(String riskRating) { this.riskRating = riskRating; }

    public String getInterpretation() { return interpretation; }
    public void setInterpretation(String interpretation) { this.interpretation = interpretation; }
}
