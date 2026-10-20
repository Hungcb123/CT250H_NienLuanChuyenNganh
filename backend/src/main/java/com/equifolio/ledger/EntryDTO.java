package com.equifolio.ledger;

import java.math.BigDecimal;

public class EntryDTO {
    private Long id;
    private Long accountId;
    private String accountCode;
    private String assetTicker;
    private String assetName;
    private BigDecimal amount;
    private BigDecimal monetaryValue;
    public BigDecimal getMonetaryValue() { return monetaryValue; }
    public void setMonetaryValue(BigDecimal value) { this.monetaryValue = value; }
    private String entryType; // "DEBIT" or "CREDIT"

    public EntryDTO() {}

    public EntryDTO(Long id, Long accountId, String accountCode, String assetTicker, String assetName, BigDecimal amount) {
        this.id = id;
        this.accountId = accountId;
        this.accountCode = accountCode;
        this.assetTicker = assetTicker;
        this.assetName = assetName;
        this.amount = amount;
        this.entryType = (amount != null && amount.compareTo(BigDecimal.ZERO) >= 0) ? "DEBIT" : "CREDIT";
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }

    public String getAccountCode() { return accountCode; }
    public void setAccountCode(String accountCode) { this.accountCode = accountCode; }

    public String getAssetTicker() { return assetTicker; }
    public void setAssetTicker(String assetTicker) { this.assetTicker = assetTicker; }

    public String getAssetName() { return assetName; }
    public void setAssetName(String assetName) { this.assetName = assetName; }

    public BigDecimal getAmount() { return amount; }
    public void setAmount(BigDecimal amount) {
        this.amount = amount;
        this.entryType = (amount != null && amount.compareTo(BigDecimal.ZERO) >= 0) ? "DEBIT" : "CREDIT";
    }

    public String getEntryType() { return entryType; }
    public void setEntryType(String entryType) { this.entryType = entryType; }
}
