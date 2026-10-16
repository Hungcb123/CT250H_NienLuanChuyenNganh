package com.equifolio.market;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

@Entity
@Table(name = "macro_indicators", uniqueConstraints = {
    @UniqueConstraint(name = "uk_macro_code_date", columnNames = {"indicator_code", "recorded_date"})
})
public class MacroIndicator {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "indicator_code", nullable = false, length = 64)
    private String indicatorCode;

    @Column(name = "indicator_name", nullable = false, length = 128)
    private String indicatorName;

    @Column(name = "indicator_value", nullable = false, precision = 10, scale = 4)
    private BigDecimal indicatorValue;

    @Column(name = "unit", length = 32)
    private String unit = "%";

    @Column(name = "recorded_date", nullable = false)
    private LocalDate recordedDate;

    @Column(name = "updated_at")
    private Instant updatedAt = Instant.now();

    public MacroIndicator() {}

    public MacroIndicator(String indicatorCode, String indicatorName, BigDecimal indicatorValue, String unit, LocalDate recordedDate) {
        this.indicatorCode = indicatorCode;
        this.indicatorName = indicatorName;
        this.indicatorValue = indicatorValue;
        this.unit = unit;
        this.recordedDate = recordedDate;
        this.updatedAt = Instant.now();
    }

    public Long getId() { return id; }
    public String getIndicatorCode() { return indicatorCode; }
    public void setIndicatorCode(String indicatorCode) { this.indicatorCode = indicatorCode; }
    public String getIndicatorName() { return indicatorName; }
    public void setIndicatorName(String indicatorName) { this.indicatorName = indicatorName; }
    public BigDecimal getIndicatorValue() { return indicatorValue; }
    public void setIndicatorValue(BigDecimal indicatorValue) { this.indicatorValue = indicatorValue; }
    public String getUnit() { return unit; }
    public void setUnit(String unit) { this.unit = unit; }
    public LocalDate getRecordedDate() { return recordedDate; }
    public void setRecordedDate(LocalDate recordedDate) { this.recordedDate = recordedDate; }
    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
