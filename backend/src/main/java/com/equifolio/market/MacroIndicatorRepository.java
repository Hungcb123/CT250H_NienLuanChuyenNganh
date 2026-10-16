package com.equifolio.market;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.Optional;

@Repository
public interface MacroIndicatorRepository extends JpaRepository<MacroIndicator, Long> {

    @Query("SELECT m FROM MacroIndicator m WHERE m.indicatorCode = :code ORDER BY m.recordedDate DESC LIMIT 1")
    Optional<MacroIndicator> findLatestByCode(@Param("code") String code);

    Optional<MacroIndicator> findByIndicatorCodeAndRecordedDate(String code, LocalDate date);
}
