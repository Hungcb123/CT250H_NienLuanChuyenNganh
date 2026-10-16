package com.equifolio.market;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Repository
public interface BankInterestRateRepository extends JpaRepository<BankInterestRate, Long> {

    @Query("SELECT b FROM BankInterestRate b WHERE b.effectiveDate = " +
           "(SELECT MAX(b2.effectiveDate) FROM BankInterestRate b2 WHERE b2.bankCode = b.bankCode AND b2.termMonths = b.termMonths) " +
           "ORDER BY b.termMonths ASC, b.interestRate DESC")
    List<BankInterestRate> findAllLatestRates();

    @Query("SELECT b FROM BankInterestRate b WHERE b.termMonths = :termMonths AND b.effectiveDate = " +
           "(SELECT MAX(b2.effectiveDate) FROM BankInterestRate b2 WHERE b2.bankCode = b.bankCode AND b2.termMonths = :termMonths) " +
           "ORDER BY b.interestRate DESC")
    List<BankInterestRate> findLatestRatesByTerm(@Param("termMonths") Integer termMonths);

    Optional<BankInterestRate> findByBankCodeAndTermMonthsAndEffectiveDate(String bankCode, Integer termMonths, LocalDate effectiveDate);
}
