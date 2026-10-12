package com.equifolio.ledger;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;

public class OpenSavingsRequest {

    @NotBlank(message = "Tên ngân hàng không được để trống")
    private String bankName;

    @NotNull(message = "Số tiền gửi không được để trống")
    @DecimalMin(value = "1000000.00", message = "Số tiền gửi tối thiểu là 1.000.000 VND")
    private BigDecimal principalAmount;

    @NotNull(message = "Lãi suất không được để trống")
    @DecimalMin(value = "0.10", message = "Lãi suất phải lớn hơn 0")
    private BigDecimal interestRate;

    @NotNull(message = "Kỳ hạn không được để trống")
    private Integer termMonths; // 1, 3, 6, 12

    private Boolean autoRollover = true;

    public OpenSavingsRequest() {}

    public String getBankName() { return bankName; }
    public void setBankName(String bankName) { this.bankName = bankName; }

    public BigDecimal getPrincipalAmount() { return principalAmount; }
    public void setPrincipalAmount(BigDecimal principalAmount) { this.principalAmount = principalAmount; }

    public BigDecimal getInterestRate() { return interestRate; }
    public void setInterestRate(BigDecimal interestRate) { this.interestRate = interestRate; }

    public Integer getTermMonths() { return termMonths; }
    public void setTermMonths(Integer termMonths) { this.termMonths = termMonths; }

    public Boolean getAutoRollover() { return autoRollover; }
    public void setAutoRollover(Boolean autoRollover) { this.autoRollover = autoRollover; }
}
