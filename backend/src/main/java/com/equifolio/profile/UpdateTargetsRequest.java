package com.equifolio.profile;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;

public class UpdateTargetsRequest {
    @NotNull(message = "Tỷ trọng Cổ phiếu không được để trống")
    @DecimalMin(value = "0.0", message = "Tỷ trọng tối thiểu là 0%")
    @DecimalMax(value = "1.0", message = "Tỷ trọng tối đa là 100%")
    private BigDecimal stock;

    @NotNull(message = "Tỷ trọng Vàng không được để trống")
    @DecimalMin(value = "0.0", message = "Tỷ trọng tối thiểu là 0%")
    @DecimalMax(value = "1.0", message = "Tỷ trọng tối đa là 100%")
    private BigDecimal gold;

    @NotNull(message = "Tỷ trọng Tiết kiệm không được để trống")
    @DecimalMin(value = "0.0", message = "Tỷ trọng tối thiểu là 0%")
    @DecimalMax(value = "1.0", message = "Tỷ trọng tối đa là 100%")
    private BigDecimal savings;

    @NotNull(message = "Tỷ trọng Tiền mặt không được để trống")
    @DecimalMin(value = "0.0", message = "Tỷ trọng tối thiểu là 0%")
    @DecimalMax(value = "1.0", message = "Tỷ trọng tối đa là 100%")
    private BigDecimal cash;

    public UpdateTargetsRequest() {}

    public UpdateTargetsRequest(BigDecimal stock, BigDecimal gold, BigDecimal savings, BigDecimal cash) {
        this.stock = stock;
        this.gold = gold;
        this.savings = savings;
        this.cash = cash;
    }

    public BigDecimal getStock() { return stock; }
    public void setStock(BigDecimal stock) { this.stock = stock; }

    public BigDecimal getGold() { return gold; }
    public void setGold(BigDecimal gold) { this.gold = gold; }

    public BigDecimal getSavings() { return savings; }
    public void setSavings(BigDecimal savings) { this.savings = savings; }

    public BigDecimal getCash() { return cash; }
    public void setCash(BigDecimal cash) { this.cash = cash; }
}
