package com.equifolio.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;

public record BankComparisonDTO(
        String bankCode,
        String bankName,
        Map<Integer, BigDecimal> ratesByTerm, // term (months) -> interest rate (%)
        LocalDate effectiveDate
) {}
