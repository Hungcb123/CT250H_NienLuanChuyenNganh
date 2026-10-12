package com.equifolio.ledger;

import java.math.BigDecimal;

public class DividendRequest {
    private String ticker;
    private String dividendType; // 'CASH' or 'STOCK'
    private BigDecimal amountPerShare; // Số tiền cổ tức trên 1 cổ phiếu (nếu có)
    private BigDecimal totalAmount; // Tổng tiền cổ tức (với CASH) hoặc Tổng số cổ phiếu thưởng (với STOCK)
    private BigDecimal taxPercent = new BigDecimal("5.0"); // Thuế TNCN 5% cho cổ tức tiền mặt ở VN
    private String notes;

    public DividendRequest() {}

    public String getTicker() { return ticker; }
    public void setTicker(String ticker) { this.ticker = ticker; }

    public String getDividendType() { return dividendType; }
    public void setDividendType(String dividendType) { this.dividendType = dividendType; }

    public BigDecimal getAmountPerShare() { return amountPerShare; }
    public void setAmountPerShare(BigDecimal amountPerShare) { this.amountPerShare = amountPerShare; }

    public BigDecimal getTotalAmount() { return totalAmount; }
    public void setTotalAmount(BigDecimal totalAmount) { this.totalAmount = totalAmount; }

    public BigDecimal getTaxPercent() { return taxPercent; }
    public void setTaxPercent(BigDecimal taxPercent) { this.taxPercent = taxPercent; }

    public String getNotes() { return notes; }
    public void setNotes(String notes) { this.notes = notes; }
}
