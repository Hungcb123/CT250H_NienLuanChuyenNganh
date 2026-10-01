package com.equifolio.profile;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface PortfolioTargetRepository extends JpaRepository<PortfolioTarget, Long> {
    List<PortfolioTarget> findByUserId(Long userId);
    Optional<PortfolioTarget> findByUserIdAndAssetClass(Long userId, String assetClass);
}
