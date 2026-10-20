package com.equifolio.ledger;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

public class LedgerAuditReportDTO {

    private int totalTransactionsChecked;
    private int balancedTransactions;
    private int unverifiedTransactions;

    public int getUnverifiedTransactions() { return unverifiedTransactions; }
    public void setUnverifiedTransactions(int value) { this.unverifiedTransactions = value; }
    private int unbalancedTransactions;
    private boolean allTransactionsBalanced;
    private boolean allAccountsConsistent;
    private String auditStatus; // 'ALL_ACID_INVARIANTS_PASSED' or 'DISCREPANCY_DETECTED'
    private String systemSummary;
    private Instant verifiedAt;

    private List<AccountAuditItem> accountAuditList = new ArrayList<>();
    private List<UnbalancedTxItem> unbalancedTxList = new ArrayList<>();

    public LedgerAuditReportDTO() {
        this.verifiedAt = Instant.now();
    }

    public static class AccountAuditItem {
        private String accountCode;
        private String assetTicker;
        private BigDecimal snapshotBalance;
        private BigDecimal calculatedEntriesBalance;
        private BigDecimal discrepancy;
        private boolean consistent;

        public AccountAuditItem() {}

        public AccountAuditItem(String accountCode, String assetTicker, BigDecimal snapshotBalance,
                                BigDecimal calculatedEntriesBalance, BigDecimal discrepancy, boolean consistent) {
            this.accountCode = accountCode;
            this.assetTicker = assetTicker;
            this.snapshotBalance = snapshotBalance;
            this.calculatedEntriesBalance = calculatedEntriesBalance;
            this.discrepancy = discrepancy;
            this.consistent = consistent;
        }

        public String getAccountCode() { return accountCode; }
        public void setAccountCode(String accountCode) { this.accountCode = accountCode; }

        public String getAssetTicker() { return assetTicker; }
        public void setAssetTicker(String assetTicker) { this.assetTicker = assetTicker; }

        public BigDecimal getSnapshotBalance() { return snapshotBalance; }
        public void setSnapshotBalance(BigDecimal snapshotBalance) { this.snapshotBalance = snapshotBalance; }

        public BigDecimal getCalculatedEntriesBalance() { return calculatedEntriesBalance; }
        public void setCalculatedEntriesBalance(BigDecimal calculatedEntriesBalance) { this.calculatedEntriesBalance = calculatedEntriesBalance; }

        public BigDecimal getDiscrepancy() { return discrepancy; }
        public void setDiscrepancy(BigDecimal discrepancy) { this.discrepancy = discrepancy; }

        public boolean isConsistent() { return consistent; }
        public void setConsistent(boolean consistent) { this.consistent = consistent; }
    }

    public static class UnbalancedTxItem {
        private String transactionCode;
        private String description;
        private BigDecimal totalDebit;
        private BigDecimal totalCredit;
        private BigDecimal imbalance;

        public UnbalancedTxItem() {}

        public UnbalancedTxItem(String transactionCode, String description, BigDecimal totalDebit, BigDecimal totalCredit, BigDecimal imbalance) {
            this.transactionCode = transactionCode;
            this.description = description;
            this.totalDebit = totalDebit;
            this.totalCredit = totalCredit;
            this.imbalance = imbalance;
        }

        public String getTransactionCode() { return transactionCode; }
        public void setTransactionCode(String transactionCode) { this.transactionCode = transactionCode; }

        public String getDescription() { return description; }
        public void setDescription(String description) { this.description = description; }

        public BigDecimal getTotalDebit() { return totalDebit; }
        public void setTotalDebit(BigDecimal totalDebit) { this.totalDebit = totalDebit; }

        public BigDecimal getTotalCredit() { return totalCredit; }
        public void setTotalCredit(BigDecimal totalCredit) { this.totalCredit = totalCredit; }

        public BigDecimal getImbalance() { return imbalance; }
        public void setImbalance(BigDecimal imbalance) { this.imbalance = imbalance; }
    }

    // Getters and Setters
    public int getTotalTransactionsChecked() { return totalTransactionsChecked; }
    public void setTotalTransactionsChecked(int totalTransactionsChecked) { this.totalTransactionsChecked = totalTransactionsChecked; }

    public int getBalancedTransactions() { return balancedTransactions; }
    public void setBalancedTransactions(int balancedTransactions) { this.balancedTransactions = balancedTransactions; }

    public int getUnbalancedTransactions() { return unbalancedTransactions; }
    public void setUnbalancedTransactions(int unbalancedTransactions) { this.unbalancedTransactions = unbalancedTransactions; }

    public boolean isAllTransactionsBalanced() { return allTransactionsBalanced; }
    public void setAllTransactionsBalanced(boolean allTransactionsBalanced) { this.allTransactionsBalanced = allTransactionsBalanced; }

    public boolean isAllAccountsConsistent() { return allAccountsConsistent; }
    public void setAllAccountsConsistent(boolean allAccountsConsistent) { this.allAccountsConsistent = allAccountsConsistent; }

    public String getAuditStatus() { return auditStatus; }
    public void setAuditStatus(String auditStatus) { this.auditStatus = auditStatus; }

    public String getSystemSummary() { return systemSummary; }
    public void setSystemSummary(String systemSummary) { this.systemSummary = systemSummary; }

    public Instant getVerifiedAt() { return verifiedAt; }
    public void setVerifiedAt(Instant verifiedAt) { this.verifiedAt = verifiedAt; }

    public List<AccountAuditItem> getAccountAuditList() { return accountAuditList; }
    public void setAccountAuditList(List<AccountAuditItem> accountAuditList) { this.accountAuditList = accountAuditList; }

    public List<UnbalancedTxItem> getUnbalancedTxList() { return unbalancedTxList; }
    public void setUnbalancedTxList(List<UnbalancedTxItem> unbalancedTxList) { this.unbalancedTxList = unbalancedTxList; }
}
