package com.equifolio.market;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface MarketPriceRepository extends JpaRepository<MarketPrice, Long> {

    @Query("SELECT mp FROM MarketPrice mp WHERE mp.asset.ticker = :ticker ORDER BY mp.tradeDate DESC LIMIT 1")
    Optional<MarketPrice> findLatestPriceByTicker(@Param("ticker") String ticker);

    @Query("SELECT mp FROM MarketPrice mp WHERE mp.tradeDate = (SELECT MAX(m.tradeDate) FROM MarketPrice m)")
    List<MarketPrice> findAllLatestPrices();
}
