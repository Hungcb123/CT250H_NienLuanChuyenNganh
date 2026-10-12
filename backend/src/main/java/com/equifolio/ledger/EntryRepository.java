package com.equifolio.ledger;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.util.List;

@Repository
public interface EntryRepository extends JpaRepository<Entry, Long> {
    List<Entry> findByTransactionId(Long transactionId);
    List<Entry> findByAccountIdOrderByCreatedAtDesc(Long accountId);

    @Query("SELECT COALESCE(SUM(e.amount), 0) FROM Entry e WHERE e.account.id = :accountId")
    BigDecimal sumAmountByAccountId(@Param("accountId") Long accountId);
}
