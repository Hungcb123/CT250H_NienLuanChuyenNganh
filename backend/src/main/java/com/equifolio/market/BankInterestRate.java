package com.equifolio.market;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

@Entity
@Table(name = "bank_interest_rates", uniqueConstraints = {
    @UniqueConstraint(name = "uk_bank_term_date", columnNames = {"bank_code", "term_months", "effective_date"})
})
public class BankInterestRate {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "bank_code", nullable = false, length = 32)
    private String bankCode;

    @Column(name = "bank_name", nullable = false, length = 128)
    private String bankName;

    @Column(name = "term_months", nullable = false)
    private Integer termMonths;

    @Column(name = "interest_rate", nullable = false, precision = 6, scale = 2)
    private BigDecimal interestRate;

    @Column(name = "effective_date", nullable = false)
    private LocalDate effectiveDate;

    @Column(name = "updated_at")
    private Instant updatedAt = Instant.now();

    public BankInterestRate() {}

    public BankInterestRate(String bankCode, String bankName, Integer termMonths, BigDecimal interestRate, LocalDate effectiveDate) {
        this.bankCode = bankCode;
        this.bankName = bankName;
        this.termMonths = termMonths;
        this.interestRate = interestRate;
        this.effectiveDate = effectiveDate;
        this.updatedAt = Instant.now();
    }

    public Long getId() { return id; }
    public String getBankCode() { return bankCode; }
    public void setBankCode(String bankCode) { this.bankCode = bankCode; }
    public String getBankName() { return bankName; }
    public void setBankName(String bankName) { this.bankName = bankName; }
    public Integer getTermMonths() { return termMonths; }
    public void setTermMonths(Integer termMonths) { this.termMonths = termMonths; }
    public BigDecimal getInterestRate() { return interestRate; }
    public void setInterestRate(BigDecimal interestRate) { this.interestRate = interestRate; }
    public LocalDate getEffectiveDate() { return effectiveDate; }
    public void setEffectiveDate(LocalDate effectiveDate) { this.effectiveDate = effectiveDate; }
    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
