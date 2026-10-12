package com.equifolio.ledger;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

public class TransactionDTO {
    private Long id;
    private String transactionCode;
    private String type;
    private String status;
    private String description;
    private Instant createdAt;
    private List<EntryDTO> entries = new ArrayList<>();
    private BigDecimal totalAmount = BigDecimal.ZERO;
    private boolean acidBalanced = true;

    public TransactionDTO() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getTransactionCode() { return transactionCode; }
    public void setTransactionCode(String transactionCode) { this.transactionCode = transactionCode; }

    public String getType() { return type; }
    public void setType(String type) { this.type = type; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }

    public List<EntryDTO> getEntries() { return entries; }
    public void setEntries(List<EntryDTO> entries) { this.entries = entries; }

    public BigDecimal getTotalAmount() { return totalAmount; }
    public void setTotalAmount(BigDecimal totalAmount) { this.totalAmount = totalAmount; }

    public boolean isAcidBalanced() { return acidBalanced; }
    public void setAcidBalanced(boolean acidBalanced) { this.acidBalanced = acidBalanced; }
}
