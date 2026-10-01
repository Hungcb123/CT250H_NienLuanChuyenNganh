package com.equifolio.optimizer;

import com.equifolio.ledger.LedgerService;
import com.equifolio.ledger.PortfolioValuationDTO;
import com.equifolio.market.MarketService;
import com.equifolio.profile.PortfolioTarget;
import com.equifolio.profile.PortfolioTargetRepository;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

@Service
public class PortfolioOptimizerService {

    private final LedgerService ledgerService;
    private final PortfolioTargetRepository portfolioTargetRepository;
    private final MarketService marketService;

    public PortfolioOptimizerService(LedgerService ledgerService,
                                     PortfolioTargetRepository portfolioTargetRepository,
                                     MarketService marketService) {
        this.ledgerService = ledgerService;
        this.portfolioTargetRepository = portfolioTargetRepository;
        this.marketService = marketService;
    }

    public RebalancePlanDTO generateRebalancePlan(Long userId) {
        PortfolioValuationDTO valuation = ledgerService.calculatePortfolioValuation(userId);
        List<PortfolioTarget> targets = portfolioTargetRepository.findByUserId(userId);

        RebalancePlanDTO plan = new RebalancePlanDTO();
        plan.setCurrentAllocations(valuation.getCurrentAllocations());

        Map<String, BigDecimal> targetMap = new HashMap<>();
        for (PortfolioTarget t : targets) {
            targetMap.put(t.getAssetClass(), t.getTargetWeight());
        }
        plan.setTargetAllocations(targetMap);

        BigDecimal totalNAV = valuation.getTotalNetWorth();
        if (totalNAV.compareTo(BigDecimal.ZERO) <= 0) {
            plan.setDriftDetected(false);
            plan.setExecutiveSummary("Danh mục chưa có tài sản nào được khai báo để thực hiện tái cơ cấu.");
            return plan;
        }

        // 1. Kiểm tra độ lệch tỷ trọng (Drift Detection > 5%)
        BigDecimal maxDrift = BigDecimal.ZERO;
        boolean isDrift = false;

        for (Map.Entry<String, BigDecimal> entry : targetMap.entrySet()) {
            String assetClass = entry.getKey();
            BigDecimal targetW = entry.getValue();
            BigDecimal currentW = valuation.getCurrentAllocations().getOrDefault(assetClass, BigDecimal.ZERO);

            BigDecimal diff = currentW.subtract(targetW).abs();
            if (diff.compareTo(maxDrift) > 0) {
                maxDrift = diff;
            }
            if (diff.compareTo(new BigDecimal("0.0500")) > 0) {
                isDrift = true;
            }
        }

        plan.setDriftDetected(isDrift);
        plan.setMaxDriftPercent(maxDrift.multiply(new BigDecimal("100")).setScale(2, RoundingMode.HALF_EVEN));

        // 2. Tính toán các hành động tái cơ cấu cụ thể
        List<RebalancePlanDTO.RebalanceAction> actions = new ArrayList<>();

        for (PortfolioValuationDTO.HoldingItem item : valuation.getHoldings()) {
            String assetClass = item.getAssetClass();
            if ("CASH".equalsIgnoreCase(assetClass)) {
                continue; // Tiền mặt làm bộ đệm điều hòa
            }

            BigDecimal currentW = item.getAllocationPercent();
            BigDecimal targetClassW = targetMap.getOrDefault(assetClass, new BigDecimal("0.3333"));

            // Đơn giản hóa: Phân bổ đều mục tiêu của nhóm cho các mã thuộc nhóm đó
            BigDecimal deltaMoney;
            BigDecimal price = item.getCurrentPrice();

            if (currentW.compareTo(targetClassW) > 0) {
                // Tỷ trọng hiện tại vượt mục tiêu -> Cần BÁN bớt (SELL)
                BigDecimal excessWeight = currentW.subtract(targetClassW);
                deltaMoney = totalNAV.multiply(excessWeight).setScale(4, RoundingMode.HALF_EVEN);

                if (price.compareTo(BigDecimal.ZERO) > 0 && deltaMoney.compareTo(new BigDecimal("1000000")) > 0) {
                    BigDecimal exactQty = deltaMoney.divide(price, 4, RoundingMode.HALF_EVEN);
                    BigDecimal roundedQty;

                    if ("STOCK".equalsIgnoreCase(assetClass)) {
                        // Làm tròn lô chẵn 100 cổ phiếu sàn HOSE
                        long lots = exactQty.longValue() / 100;
                        roundedQty = BigDecimal.valueOf(lots * 100);
                    } else if ("GOLD".equalsIgnoreCase(assetClass)) {
                        // Làm tròn bước chỉ vàng nguyên
                        roundedQty = BigDecimal.valueOf(exactQty.longValue());
                    } else {
                        roundedQty = exactQty.setScale(0, RoundingMode.FLOOR);
                    }

                    if (roundedQty.compareTo(BigDecimal.ZERO) > 0) {
                        BigDecimal totalEst = roundedQty.multiply(price).setScale(0, RoundingMode.HALF_EVEN);
                        actions.add(new RebalancePlanDTO.RebalanceAction(
                                "SELL",
                                item.getTicker(),
                                item.getAssetName(),
                                assetClass,
                                exactQty,
                                roundedQty,
                                price,
                                totalEst,
                                "Tỷ trọng nhóm " + assetClass + " hiện tại đang vượt mục tiêu " + excessWeight.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN) + "%. Khuyến nghị chốt lời để bảo vệ vốn."
                        ));
                    }
                }
            }
        }

        // Tóm tắt kế hoạch
        if (isDrift) {
            plan.setExecutiveSummary("Phát hiện tỷ trọng danh mục lệch " + plan.getMaxDriftPercent() + "% so với mục tiêu SAA. Đề xuất thực hiện các lệnh điều chỉnh lô chẵn bên dưới và gửi phần tiền dôi dư vào Tiết kiệm ngân hàng.");
        } else {
            plan.setExecutiveSummary("Danh mục hiện tại đang duy trì trạng thái cân bằng tốt (Độ lệch tối đa " + plan.getMaxDriftPercent() + "% < 5%). Khuyến nghị tiếp tục nắm giữ kỷ luật.");
        }

        plan.setActions(actions);
        return plan;
    }
}
