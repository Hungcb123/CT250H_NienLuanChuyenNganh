package com.equifolio.ledger;

import com.equifolio.market.Asset;
import com.equifolio.profile.User;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;

@Entity
@Table(name = "accounts", uniqueConstraints = {
    @UniqueConstraint(name = "uk_user_account", columnNames = {"user_id", "account_code"})
})
public class Account {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "account_code", nullable = false, length = 64)
    private String accountCode; // 'VND_WALLET', 'EQUITY_CAPITAL', 'STOCK_HPG', 'GOLD_SJC'

    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "asset_type", nullable = false)
    private Asset asset;

    @Column(nullable = false, precision = 19, scale = 4)
    private BigDecimal balance = BigDecimal.ZERO;

    @Version
    @Column(nullable = false)
    private Long version = 0L; // Optimistic Locking

    @Column(name = "created_at")
    private Instant createdAt = Instant.now();

    public Account() {}

    public Account(User user, String accountCode, Asset asset, BigDecimal balance) {
        this.user = user;
        this.accountCode = accountCode;
        this.asset = asset;
        this.balance = balance;
        this.version = 0L;
        this.createdAt = Instant.now();
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public User getUser() { return user; }
    public void setUser(User user) { this.user = user; }

    public String getAccountCode() { return accountCode; }
    public void setAccountCode(String accountCode) { this.accountCode = accountCode; }

    public Asset getAsset() { return asset; }
    public void setAsset(Asset asset) { this.asset = asset; }

    public BigDecimal getBalance() { return balance; }
    public void setBalance(BigDecimal balance) { this.balance = balance; }

    public Long getVersion() { return version; }
    public void setVersion(Long version) { this.version = version; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
