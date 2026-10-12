package com.equifolio.ledger;

import com.equifolio.profile.User;
import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

@Entity
@Table(name = "portfolio_snapshots", uniqueConstraints = {
    @UniqueConstraint(name = "uk_user_snapshot_date", columnNames = {"user_id", "snapshot_date"})
})
public class PortfolioSnapshot {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "snapshot_date", nullable = false)
    private LocalDate snapshotDate;

    @Column(name = "total_nav", nullable = false, precision = 19, scale = 4)
    private BigDecimal totalNav = BigDecimal.ZERO;

    @Column(name = "stock_value", precision = 19, scale = 4)
    private BigDecimal stockValue = BigDecimal.ZERO;

    @Column(name = "gold_value", precision = 19, scale = 4)
    private BigDecimal goldValue = BigDecimal.ZERO;

    @Column(name = "savings_value", precision = 19, scale = 4)
    private BigDecimal savingsValue = BigDecimal.ZERO;

    @Column(name = "cash_value", precision = 19, scale = 4)
    private BigDecimal cashValue = BigDecimal.ZERO;

    @Column(name = "vnindex_value", precision = 19, scale = 4)
    private BigDecimal vnindexValue = new BigDecimal("1280.0000");

    @Column(name = "created_at")
    private Instant createdAt = Instant.now();

    public PortfolioSnapshot() {}

    public PortfolioSnapshot(User user, LocalDate snapshotDate, BigDecimal totalNav,
                             BigDecimal stockValue, BigDecimal goldValue, BigDecimal savingsValue,
                             BigDecimal cashValue, BigDecimal vnindexValue) {
        this.user = user;
        this.snapshotDate = snapshotDate;
        this.totalNav = totalNav;
        this.stockValue = stockValue;
        this.goldValue = goldValue;
        this.savingsValue = savingsValue;
        this.cashValue = cashValue;
        this.vnindexValue = vnindexValue != null ? vnindexValue : new BigDecimal("1280.0000");
        this.createdAt = Instant.now();
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public User getUser() { return user; }
    public void setUser(User user) { this.user = user; }

    public LocalDate getSnapshotDate() { return snapshotDate; }
    public void setSnapshotDate(LocalDate snapshotDate) { this.snapshotDate = snapshotDate; }

    public BigDecimal getTotalNav() { return totalNav; }
    public void setTotalNav(BigDecimal totalNav) { this.totalNav = totalNav; }

    public BigDecimal getStockValue() { return stockValue; }
    public void setStockValue(BigDecimal stockValue) { this.stockValue = stockValue; }

    public BigDecimal getGoldValue() { return goldValue; }
    public void setGoldValue(BigDecimal goldValue) { this.goldValue = goldValue; }

    public BigDecimal getSavingsValue() { return savingsValue; }
    public void setSavingsValue(BigDecimal savingsValue) { this.savingsValue = savingsValue; }

    public BigDecimal getCashValue() { return cashValue; }
    public void setCashValue(BigDecimal cashValue) { this.cashValue = cashValue; }

    public BigDecimal getVnindexValue() { return vnindexValue; }
    public void setVnindexValue(BigDecimal vnindexValue) { this.vnindexValue = vnindexValue; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
