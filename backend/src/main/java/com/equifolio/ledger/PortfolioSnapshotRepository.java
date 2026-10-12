package com.equifolio.ledger;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Repository
public interface PortfolioSnapshotRepository extends JpaRepository<PortfolioSnapshot, Long> {

    List<PortfolioSnapshot> findByUserIdOrderBySnapshotDateAsc(Long userId);

    List<PortfolioSnapshot> findByUserIdAndSnapshotDateGreaterThanEqualOrderBySnapshotDateAsc(Long userId, LocalDate fromDate);

    Optional<PortfolioSnapshot> findByUserIdAndSnapshotDate(Long userId, LocalDate snapshotDate);
}
