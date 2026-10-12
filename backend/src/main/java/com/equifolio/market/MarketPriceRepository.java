package com.equifolio.market;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Repository
public interface MarketPriceRepository extends JpaRepository<MarketPrice, Long> {

    @Query("SELECT mp FROM MarketPrice mp WHERE mp.asset.ticker = :ticker ORDER BY mp.tradeDate DESC LIMIT 1")
    Optional<MarketPrice> findLatestPriceByTicker(@Param("ticker") String ticker);

    @Query(value = "SELECT DISTINCT ON (ticker) * FROM market_prices ORDER BY ticker, trade_date DESC", nativeQuery = true)
    List<MarketPrice> findAllLatestPrices();

    Optional<MarketPrice> findByAsset_TickerAndTradeDate(String ticker, LocalDate tradeDate);

    @Query("SELECT MAX(mp.tradeDate) FROM MarketPrice mp WHERE mp.asset.ticker = :ticker")
    Optional<LocalDate> findMaxTradeDateByTicker(@Param("ticker") String ticker);

    List<MarketPrice> findByAsset_TickerOrderByTradeDateAsc(String ticker);
}
