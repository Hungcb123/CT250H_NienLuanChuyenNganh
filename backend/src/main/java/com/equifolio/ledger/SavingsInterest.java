package com.equifolio.ledger;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;

/** Application policy: early withdrawals use the configured annual demand rate. */
public final class SavingsInterest {
    private SavingsInterest() {}

    public static BigDecimal accrued(SavingsDeposit deposit, LocalDate date, BigDecimal earlyRate) {
        if (deposit.getStartDate() == null || deposit.getMaturityDate() == null)
            throw new IllegalStateException("Sổ tiết kiệm thiếu ngày gửi hoặc ngày đáo hạn");
        boolean early = date.isBefore(deposit.getMaturityDate());
        LocalDate end = early ? date : deposit.getMaturityDate();
        long days = Math.max(0, ChronoUnit.DAYS.between(deposit.getStartDate(), end));
        BigDecimal rate = early ? earlyRate : deposit.getInterestRate();
        if (rate == null || rate.signum() < 0) throw new IllegalStateException("Lãi suất tất toán không hợp lệ");
        return deposit.getPrincipalAmount().multiply(rate).multiply(BigDecimal.valueOf(days))
                .divide(new BigDecimal("36500"), 0, RoundingMode.HALF_EVEN);
    }
}
