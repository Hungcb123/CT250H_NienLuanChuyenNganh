package com.equifolio.ledger;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;

public class EquityInjectionRequest {

    @NotBlank(message = "Mã tài sản không được để trống")
    private String ticker; // 'VND', 'HPG', 'GOLD_SJC'

    @NotNull(message = "Số lượng/số tiền không được để trống")
    @DecimalMin(value = "0.0001", message = "Số lượng phải lớn hơn 0")
    private BigDecimal amount; // Số lượng CP hoặc Vàng, hoặc số tiền VND

    private BigDecimal entryPrice; // Giá vốn tại thời điểm mua (nếu là cổ phiếu/vàng)

    private String description;

    public EquityInjectionRequest() {}

    public String getTicker() { return ticker; }
    public void setTicker(String ticker) { this.ticker = ticker; }

    public BigDecimal getAmount() { return amount; }
    public void setAmount(BigDecimal amount) { this.amount = amount; }

    public BigDecimal getEntryPrice() { return entryPrice; }
    public void setEntryPrice(BigDecimal entryPrice) { this.entryPrice = entryPrice; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
}
