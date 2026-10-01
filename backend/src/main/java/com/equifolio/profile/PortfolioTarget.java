package com.equifolio.profile;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;

@Entity
@Table(name = "portfolio_targets", uniqueConstraints = {
    @UniqueConstraint(name = "uk_user_target_class", columnNames = {"user_id", "asset_class"})
})
public class PortfolioTarget {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "asset_class", nullable = false, length = 32)
    private String assetClass; // 'STOCK', 'GOLD', 'CASH_SAVINGS'

    @Column(name = "target_weight", nullable = false, precision = 5, scale = 4)
    private BigDecimal targetWeight; // Ví dụ: 0.3500 (35%)

    @Column(name = "updated_at")
    private Instant updatedAt = Instant.now();

    public PortfolioTarget() {}

    public PortfolioTarget(User user, String assetClass, BigDecimal targetWeight) {
        this.user = user;
        this.assetClass = assetClass;
        this.targetWeight = targetWeight;
        this.updatedAt = Instant.now();
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public User getUser() { return user; }
    public void setUser(User user) { this.user = user; }

    public String getAssetClass() { return assetClass; }
    public void setAssetClass(String assetClass) { this.assetClass = assetClass; }

    public BigDecimal getTargetWeight() { return targetWeight; }
    public void setTargetWeight(BigDecimal targetWeight) { this.targetWeight = targetWeight; }

    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
