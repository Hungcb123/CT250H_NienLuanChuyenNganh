package com.equifolio.ledger;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;

@Repository
public interface SavingsDepositRepository extends JpaRepository<SavingsDeposit, Long> {
    List<SavingsDeposit> findByUserIdAndStatus(Long userId, String status);
    List<SavingsDeposit> findByStatusAndMaturityDateLessThanEqual(String status, LocalDate date);
}
