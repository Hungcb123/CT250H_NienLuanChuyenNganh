package com.equifolio.ledger;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import java.math.BigDecimal;

public class TradeOrderRequest {

    @NotBlank(message = "Mã tài sản không được để trống")
    private String ticker;

    @NotBlank(message = "Loại lệnh không được để trống")
    @Pattern(regexp = "^(BUY|SELL)$", message = "Loại lệnh chỉ có thể là BUY hoặc SELL")
    private String actionType; // 'BUY' hoặc 'SELL'

    @NotNull(message = "Khối lượng đặt lệnh không được để trống")
    @DecimalMin(value = "0.0001", message = "Khối lượng phải lớn hơn 0")
    private BigDecimal quantity;

    @NotNull(message = "Giá đặt lệnh không được để trống")
    @DecimalMin(value = "1.0", message = "Giá đặt lệnh phải lớn hơn 0")
    private BigDecimal price;

    private String notes;

    public TradeOrderRequest() {}

    public TradeOrderRequest(String ticker, String actionType, BigDecimal quantity, BigDecimal price, String notes) {
        this.ticker = ticker;
        this.actionType = actionType;
        this.quantity = quantity;
        this.price = price;
        this.notes = notes;
    }

    public String getTicker() { return ticker; }
    public void setTicker(String ticker) { this.ticker = ticker; }

    public String getActionType() { return actionType; }
    public void setActionType(String actionType) { this.actionType = actionType; }

    public BigDecimal getQuantity() { return quantity; }
    public void setQuantity(BigDecimal quantity) { this.quantity = quantity; }

    public BigDecimal getPrice() { return price; }
    public void setPrice(BigDecimal price) { this.price = price; }

    public String getNotes() { return notes; }
    public void setNotes(String notes) { this.notes = notes; }
}
