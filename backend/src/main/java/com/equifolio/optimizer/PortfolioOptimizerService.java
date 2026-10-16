package com.equifolio.optimizer;

import com.equifolio.ledger.*;
import com.equifolio.market.Asset;
import com.equifolio.market.AssetRepository;
import com.equifolio.market.MarketService;
import com.equifolio.profile.PortfolioTarget;
import com.equifolio.profile.PortfolioTargetRepository;
import com.equifolio.profile.User;
import com.equifolio.profile.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

@Service
public class PortfolioOptimizerService {

    private final LedgerService ledgerService;
    private final PortfolioTargetRepository portfolioTargetRepository;
    private final MarketService marketService;
    private final AccountRepository accountRepository;
    private final TransactionRepository transactionRepository;
    private final UserRepository userRepository;
    private final AssetRepository assetRepository;
    private final OnnxRegimeService onnxRegimeService;
    private final SavingsDepositRepository savingsDepositRepository;

    public PortfolioOptimizerService(LedgerService ledgerService,
                                     PortfolioTargetRepository portfolioTargetRepository,
                                     MarketService marketService,
                                     AccountRepository accountRepository,
                                     TransactionRepository transactionRepository,
                                     UserRepository userRepository,
                                     AssetRepository assetRepository,
                                     OnnxRegimeService onnxRegimeService,
                                     SavingsDepositRepository savingsDepositRepository) {
        this.ledgerService = ledgerService;
        this.portfolioTargetRepository = portfolioTargetRepository;
        this.marketService = marketService;
        this.accountRepository = accountRepository;
        this.transactionRepository = transactionRepository;
        this.userRepository = userRepository;
        this.assetRepository = assetRepository;
        this.onnxRegimeService = onnxRegimeService;
        this.savingsDepositRepository = savingsDepositRepository;
    }

    /** Biên độ dịch chuyển tối đa TAA: ±15% quanh SAA */
    private static final BigDecimal DELTA_W_MAX = new BigDecimal("0.15");

    /** Biên độ dịch chuyển tối đa cho Vàng: ±10% (thận trọng hơn cổ phiếu) */
    private static final BigDecimal DELTA_W_MAX_GOLD = new BigDecimal("0.10");

    /**
     * Tính tỷ trọng TAA cho một lớp tài sản:
     * w_TAA = clamp(w_SAA + Δw, w_SAA - deltaMax, w_SAA + deltaMax)
     * Trong đó: Δw = signal × confidence × deltaMax
     */
    private BigDecimal calculateTaaWeight(BigDecimal saaw, RegimePrediction prediction, BigDecimal deltaMax) {
        BigDecimal delta = deltaMax
                .multiply(BigDecimal.valueOf(prediction.signal()))
                .multiply(BigDecimal.valueOf(prediction.confidence()))
                .setScale(4, RoundingMode.HALF_EVEN);

        BigDecimal taaRaw = saaw.add(delta);
        BigDecimal lower = saaw.subtract(deltaMax).max(BigDecimal.ZERO);
        BigDecimal upper = saaw.add(deltaMax).min(BigDecimal.ONE);

        return taaRaw.max(lower).min(upper).setScale(4, RoundingMode.HALF_EVEN);
    }

    public RebalancePlanDTO generateRebalancePlan(Long userId) {
        PortfolioValuationDTO valuation = ledgerService.calculatePortfolioValuation(userId);
        List<PortfolioTarget> targets = portfolioTargetRepository.findByUserId(userId);

        RebalancePlanDTO plan = new RebalancePlanDTO();
        plan.setCurrentAllocations(valuation.getCurrentAllocations());

        // ═══ SAA: Đọc tỷ trọng mỏ neo (cố định từ khảo sát) ═══
        Map<String, BigDecimal> saaMap = new HashMap<>();
        for (PortfolioTarget t : targets) {
            saaMap.put(t.getAssetClass(), t.getTargetWeight());
        }
        plan.setSaaTargets(new HashMap<>(saaMap));

        // ═══ ML: Gọi ONNX dự báo regime T+20 ═══
        RegimePrediction stockPrediction = onnxRegimeService.predictStockRegime();
        RegimePrediction goldPrediction = onnxRegimeService.predictGoldRegime();

        // ═══ TAA: Dịch chuyển tỷ trọng theo ML ═══
        BigDecimal saawStock = saaMap.getOrDefault("STOCK", new BigDecimal("0.35"));
        BigDecimal saawGold = saaMap.getOrDefault("GOLD", new BigDecimal("0.35"));

        BigDecimal taawStock = calculateTaaWeight(saawStock, stockPrediction, DELTA_W_MAX);
        BigDecimal taawGold = calculateTaaWeight(saawGold, goldPrediction, DELTA_W_MAX_GOLD);

        // Phần còn lại (CASH_SAVINGS) = 1.0 - STOCK - GOLD
        BigDecimal taawCashSavings = BigDecimal.ONE.subtract(taawStock).subtract(taawGold)
                .max(BigDecimal.ZERO).setScale(4, RoundingMode.HALF_EVEN);

        // Phân chia CASH_SAVINGS thành SAVINGS và CASH theo tỷ lệ SAA gốc
        BigDecimal saawSavings = saaMap.getOrDefault("SAVINGS", new BigDecimal("0.20"));
        BigDecimal saawCash = saaMap.getOrDefault("CASH", new BigDecimal("0.10"));
        BigDecimal cashSavingsTotal = saawSavings.add(saawCash);
        BigDecimal savingsRatio = (cashSavingsTotal.compareTo(BigDecimal.ZERO) > 0)
                ? saawSavings.divide(cashSavingsTotal, 4, RoundingMode.HALF_EVEN)
                : new BigDecimal("0.6667");
        BigDecimal taawSavings = taawCashSavings.multiply(savingsRatio).setScale(4, RoundingMode.HALF_EVEN);
        BigDecimal taawCash = taawCashSavings.subtract(taawSavings);

        // Build TAA target map
        Map<String, BigDecimal> taaMap = new HashMap<>();
        taaMap.put("STOCK", taawStock);
        taaMap.put("GOLD", taawGold);
        taaMap.put("SAVINGS", taawSavings);
        taaMap.put("CASH", taawCash);
        taaMap.put("CASH_SAVINGS", taawCashSavings);

        plan.setTaaTargets(new HashMap<>(taaMap));

        // targetAllocations = TAA targets (for backward compat — Frontend reads this field)
        plan.setTargetAllocations(taaMap);

        // ═══ ML Predictions info ═══
        BigDecimal stockDelta = taawStock.subtract(saawStock);
        BigDecimal goldDelta = taawGold.subtract(saawGold);

        List<RebalancePlanDTO.MlPredictionInfo> mlInfoList = new ArrayList<>();
        mlInfoList.add(new RebalancePlanDTO.MlPredictionInfo(
                "STOCK", "stock_regime.onnx",
                stockPrediction.signal(), stockPrediction.confidence(),
                stockPrediction.regimeName(), stockDelta));
        mlInfoList.add(new RebalancePlanDTO.MlPredictionInfo(
                "GOLD", "gold_trend.onnx",
                goldPrediction.signal(), goldPrediction.confidence(),
                goldPrediction.regimeName(), goldDelta));
        plan.setMlPredictions(mlInfoList);

        // ═══ Tiếp tục dùng taaMap (thay vì saaMap) cho Drift Detection & Actions ═══
        Map<String, BigDecimal> targetMap = taaMap;

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
        BigDecimal totalSoldEst = BigDecimal.ZERO;

        // A. Xét các nhóm tài sản VƯỢT tỷ trọng mục tiêu -> BÁN (SELL) theo tỷ lệ thành phần
        for (Map.Entry<String, BigDecimal> entry : targetMap.entrySet()) {
            String assetClass = entry.getKey();
            if ("CASH".equalsIgnoreCase(assetClass) || "CASH_SAVINGS".equalsIgnoreCase(assetClass)) {
                continue;
            }
            BigDecimal targetW = entry.getValue();
            BigDecimal currentClassW = valuation.getCurrentAllocations().getOrDefault(assetClass, BigDecimal.ZERO);
            if (currentClassW.compareTo(targetW.add(new BigDecimal("0.0200"))) > 0) {
                BigDecimal excessClassWeight = currentClassW.subtract(targetW);
                BigDecimal totalClassExcessMoney = totalNAV.multiply(excessClassWeight).setScale(4, RoundingMode.HALF_EVEN);

                if ("SAVINGS".equalsIgnoreCase(assetClass)) {
                    // Tiết kiệm vượt mục tiêu -> Đề xuất tất toán bớt các sổ tiết kiệm gần ngày đáo hạn nhất
                    List<SavingsDeposit> activeDeposits = savingsDepositRepository.findByUserIdAndStatus(userId, "ACTIVE");
                    if (activeDeposits != null && !activeDeposits.isEmpty()) {
                        List<SavingsDeposit> sortedDeposits = activeDeposits.stream()
                                .sorted(Comparator.comparing(SavingsDeposit::getMaturityDate))
                                .toList();

                        BigDecimal accumulatedSettle = BigDecimal.ZERO;
                        for (SavingsDeposit dep : sortedDeposits) {
                            if (accumulatedSettle.compareTo(totalClassExcessMoney) >= 0) {
                                break;
                            }
                            BigDecimal principal = dep.getPrincipalAmount();
                            accumulatedSettle = accumulatedSettle.add(principal);
                            totalSoldEst = totalSoldEst.add(principal);

                            RebalancePlanDTO.RebalanceAction action = new RebalancePlanDTO.RebalanceAction(
                                    "SETTLE_SAVINGS",
                                    String.valueOf(dep.getId()),
                                    "Tất toán sổ " + dep.getBankName() + " (" + dep.getTermMonths() + "T)",
                                    "SAVINGS",
                                    BigDecimal.ONE,
                                    principal,
                                    principal,
                                    principal,
                                    "Tỷ trọng Tiết kiệm (" + currentClassW.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN) +
                                            "%) vượt mục tiêu (" + targetW.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN) +
                                            "%). Khuyến nghị tất toán sổ đáo hạn " + dep.getMaturityDate() +
                                            " để thu hồi vốn nạp vào ví tiền mặt giải ngân tái cơ cấu."
                            );
                            action.setEstimatedFee(BigDecimal.ZERO);
                            action.setEstimatedTax(BigDecimal.ZERO);
                            action.setNetMoney(principal);
                            actions.add(action);
                        }
                    }
                } else {
                    BigDecimal totalClassValue = "STOCK".equalsIgnoreCase(assetClass)
                            ? valuation.getStockValue()
                            : ("GOLD".equalsIgnoreCase(assetClass) ? valuation.getGoldValue() : BigDecimal.ZERO);

                    if (totalClassValue.compareTo(BigDecimal.ZERO) > 0) {
                        for (PortfolioValuationDTO.HoldingItem item : valuation.getHoldings()) {
                            if (assetClass.equalsIgnoreCase(item.getAssetClass())) {
                                BigDecimal itemShareInClass = item.getMarketValue().divide(totalClassValue, 4, RoundingMode.HALF_EVEN);
                                BigDecimal itemTrimMoney = totalClassExcessMoney.multiply(itemShareInClass).setScale(4, RoundingMode.HALF_EVEN);
                                BigDecimal price = item.getCurrentPrice();

                                if (price.compareTo(BigDecimal.ZERO) > 0 && itemTrimMoney.compareTo(new BigDecimal("500000")) > 0) {
                                    BigDecimal exactQty = itemTrimMoney.divide(price, 4, RoundingMode.HALF_EVEN);
                                    BigDecimal roundedQty;

                                    if ("STOCK".equalsIgnoreCase(assetClass)) {
                                        long lots = exactQty.longValue() / 100;
                                        roundedQty = BigDecimal.valueOf(lots * 100);
                                    } else if ("GOLD".equalsIgnoreCase(assetClass)) {
                                        roundedQty = BigDecimal.valueOf(exactQty.longValue());
                                    } else {
                                        roundedQty = exactQty.setScale(0, RoundingMode.FLOOR);
                                    }

                                    if (roundedQty.compareTo(BigDecimal.ZERO) > 0) {
                                        BigDecimal totalEst = roundedQty.multiply(price).setScale(0, RoundingMode.HALF_EVEN);
                                        BigDecimal fee = totalEst.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
                                        BigDecimal tax = totalEst.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
                                        BigDecimal net = totalEst.subtract(fee).subtract(tax);

                                        totalSoldEst = totalSoldEst.add(totalEst);
                                        RebalancePlanDTO.RebalanceAction action = new RebalancePlanDTO.RebalanceAction(
                                                "SELL",
                                                item.getTicker(),
                                                item.getAssetName(),
                                                assetClass,
                                                exactQty,
                                                roundedQty,
                                                price,
                                                totalEst,
                                                "Tỷ trọng nhóm " + assetClass + " đang vượt mục tiêu " +
                                                        excessClassWeight.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN) +
                                                        "%. Khuyến nghị chốt lời lô chẵn sàn HOSE để bảo toàn vốn."
                                        );
                                        action.setEstimatedFee(fee);
                                        action.setEstimatedTax(tax);
                                        action.setNetMoney(net);
                                        actions.add(action);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // B. Xét các tài sản DƯỚI tỷ trọng mục tiêu -> MUA (BUY)
        BigDecimal availableCashForBuying = valuation.getCashBalance().add(totalSoldEst);

        for (Map.Entry<String, BigDecimal> entry : targetMap.entrySet()) {
            String assetClass = entry.getKey();
            BigDecimal targetW = entry.getValue();
            BigDecimal currentClassW = valuation.getCurrentAllocations().getOrDefault(assetClass, BigDecimal.ZERO);

            if (targetW.compareTo(currentClassW.add(new BigDecimal("0.0200"))) > 0) {
                BigDecimal deficitWeight = targetW.subtract(currentClassW);
                BigDecimal deficitMoney = totalNAV.multiply(deficitWeight).setScale(4, RoundingMode.HALF_EVEN);

                if ("GOLD".equalsIgnoreCase(assetClass)) {
                    BigDecimal goldPrice = marketService.getLatestPrice("GOLD_SJC");
                    if (goldPrice.compareTo(BigDecimal.ZERO) > 0) {
                        BigDecimal availableForGold = availableCashForBuying.min(deficitMoney);
                        if (availableForGold.compareTo(goldPrice) >= 0) {
                            long affordableGoldQty = availableForGold.divide(goldPrice, 0, RoundingMode.FLOOR).longValue();
                            BigDecimal roundedGoldQty = BigDecimal.valueOf(affordableGoldQty);
                            if (roundedGoldQty.compareTo(BigDecimal.ZERO) > 0) {
                                BigDecimal totalEst = roundedGoldQty.multiply(goldPrice).setScale(0, RoundingMode.HALF_EVEN);
                                BigDecimal fee = totalEst.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
                                BigDecimal net = totalEst.add(fee);
                                availableCashForBuying = availableCashForBuying.subtract(net);

                                RebalancePlanDTO.RebalanceAction action = new RebalancePlanDTO.RebalanceAction(
                                        "BUY",
                                        "GOLD_SJC",
                                        "Vàng miếng SJC 999.9",
                                        "GOLD",
                                        BigDecimal.valueOf(affordableGoldQty),
                                        roundedGoldQty,
                                        goldPrice,
                                        totalEst,
                                        "Tỷ trọng nhóm Vàng hiện đang thiếu " +
                                                deficitWeight.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN) +
                                                "%. Khuyến nghị dùng tiền mặt khả dụng mua tích lũy " + roundedGoldQty + " chỉ SJC để phòng vệ rủi ro vĩ mô."
                                );
                                action.setEstimatedFee(fee);
                                action.setEstimatedTax(BigDecimal.ZERO);
                                action.setNetMoney(net);
                                actions.add(action);
                            }
                        }
                    }
                } else if ("STOCK".equalsIgnoreCase(assetClass)) {
                    // Mua cổ phiếu theo tỷ lệ các mã hiện có trong danh mục (hoặc ETF VN30 nếu chưa có mã nào)
                    BigDecimal availableForStock = availableCashForBuying.min(deficitMoney);
                    BigDecimal totalStockValue = valuation.getStockValue();

                    if (availableForStock.compareTo(new BigDecimal("1000000")) >= 0) { // Tối thiểu 1 triệu để đủ mua lô chẵn
                        List<PortfolioValuationDTO.HoldingItem> stockHoldings = valuation.getHoldings().stream()
                                .filter(h -> "STOCK".equalsIgnoreCase(h.getAssetClass()))
                                .toList();

                        if (!stockHoldings.isEmpty() && totalStockValue.compareTo(BigDecimal.ZERO) > 0) {
                            for (PortfolioValuationDTO.HoldingItem item : stockHoldings) {
                                BigDecimal itemShare = item.getMarketValue().divide(totalStockValue, 4, RoundingMode.HALF_EVEN);
                                BigDecimal itemBuyBudget = availableForStock.multiply(itemShare).setScale(0, RoundingMode.FLOOR);
                                BigDecimal price = item.getCurrentPrice();

                                if (price.compareTo(BigDecimal.ZERO) > 0) {
                                    BigDecimal unitCost = price.multiply(new BigDecimal("1.001"));
                                    long affordableLots = itemBuyBudget.divide(unitCost, 0, RoundingMode.FLOOR).longValue() / 100;
                                    BigDecimal roundedQty = BigDecimal.valueOf(affordableLots * 100);

                                    if (roundedQty.compareTo(BigDecimal.ZERO) > 0) {
                                        BigDecimal exactQty = itemBuyBudget.divide(price, 4, RoundingMode.HALF_EVEN);
                                        BigDecimal totalEst = roundedQty.multiply(price).setScale(0, RoundingMode.HALF_EVEN);
                                        BigDecimal fee = totalEst.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
                                        BigDecimal net = totalEst.add(fee);

                                        String note = "Tỷ trọng Cổ phiếu đang thiếu " +
                                                deficitWeight.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN) +
                                                "%. Khuyến nghị dùng tiền mặt khả dụng mua thêm " + roundedQty + " CP " + item.getTicker() +
                                                " (lô chẵn HOSE) để tăng tỷ trọng theo tín hiệu TAA.";

                                        RebalancePlanDTO.RebalanceAction action = new RebalancePlanDTO.RebalanceAction(
                                                "BUY",
                                                item.getTicker(),
                                                item.getAssetName(),
                                                "STOCK",
                                                exactQty,
                                                roundedQty,
                                                price,
                                                totalEst,
                                                note
                                        );
                                        action.setEstimatedFee(fee);
                                        action.setEstimatedTax(BigDecimal.ZERO);
                                        action.setNetMoney(net);
                                        actions.add(action);
                                    }
                                }
                            }

                            // Nếu chia nhỏ dẫn đến các mã đều < 100 CP, dồn ngân sách vào mã có giá trị lớn nhất trong rổ
                            if (actions.stream().noneMatch(a -> "STOCK".equalsIgnoreCase(a.getAssetClass()))) {
                                PortfolioValuationDTO.HoldingItem largestHolding = stockHoldings.stream()
                                        .max(Comparator.comparing(PortfolioValuationDTO.HoldingItem::getMarketValue))
                                        .orElse(null);
                                if (largestHolding != null && largestHolding.getCurrentPrice().compareTo(BigDecimal.ZERO) > 0) {
                                    BigDecimal price = largestHolding.getCurrentPrice();
                                    BigDecimal unitCost = price.multiply(new BigDecimal("1.001"));
                                    long affordableLots = availableForStock.divide(unitCost, 0, RoundingMode.FLOOR).longValue() / 100;
                                    BigDecimal roundedQty = BigDecimal.valueOf(affordableLots * 100);
                                    if (roundedQty.compareTo(BigDecimal.ZERO) > 0) {
                                        BigDecimal exactQty = availableForStock.divide(price, 4, RoundingMode.HALF_EVEN);
                                        BigDecimal totalEst = roundedQty.multiply(price).setScale(0, RoundingMode.HALF_EVEN);
                                        BigDecimal fee = totalEst.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
                                        BigDecimal net = totalEst.add(fee);

                                        RebalancePlanDTO.RebalanceAction action = new RebalancePlanDTO.RebalanceAction(
                                                "BUY",
                                                largestHolding.getTicker(),
                                                largestHolding.getAssetName(),
                                                "STOCK",
                                                exactQty,
                                                roundedQty,
                                                price,
                                                totalEst,
                                                "Tập trung vốn tiền mặt mua thêm " + roundedQty + " CP " + largestHolding.getTicker() +
                                                        " (lô chẵn HOSE) để nâng tỷ trọng Cổ phiếu theo mục tiêu TAA."
                                        );
                                        action.setEstimatedFee(fee);
                                        action.setEstimatedTax(BigDecimal.ZERO);
                                        action.setNetMoney(net);
                                        actions.add(action);
                                    }
                                }
                            }
                        } else {
                            // Chưa có cổ phiếu nào trong danh mục -> Khuyến nghị mua chứng chỉ quỹ VN30 ETF (E1VFVN30)
                            String etfTicker = "E1VFVN30";
                            BigDecimal etfPrice = marketService.getLatestPrice(etfTicker);
                            if (etfPrice.compareTo(BigDecimal.ZERO) <= 0) {
                                etfPrice = new BigDecimal("22500");
                            }
                            BigDecimal unitCost = etfPrice.multiply(new BigDecimal("1.001"));
                            long affordableLots = availableForStock.divide(unitCost, 0, RoundingMode.FLOOR).longValue() / 100;
                            BigDecimal roundedQty = BigDecimal.valueOf(affordableLots * 100);

                            if (roundedQty.compareTo(BigDecimal.ZERO) > 0) {
                                BigDecimal exactQty = availableForStock.divide(etfPrice, 4, RoundingMode.HALF_EVEN);
                                BigDecimal totalEst = roundedQty.multiply(etfPrice).setScale(0, RoundingMode.HALF_EVEN);
                                BigDecimal fee = totalEst.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
                                BigDecimal net = totalEst.add(fee);

                                RebalancePlanDTO.RebalanceAction action = new RebalancePlanDTO.RebalanceAction(
                                        "BUY",
                                        etfTicker,
                                        "Quỹ ETF VN30 (E1VFVN30)",
                                        "STOCK",
                                        exactQty,
                                        roundedQty,
                                        etfPrice,
                                        totalEst,
                                        "Tỷ trọng Cổ phiếu đang thiếu " +
                                                deficitWeight.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN) +
                                                "%. Khuyến nghị mua " + roundedQty + " CCQ E1VFVN30 đại diện rổ VN30 để bám sát chỉ số và tín hiệu TAA."
                                );
                                action.setEstimatedFee(fee);
                                action.setEstimatedTax(BigDecimal.ZERO);
                                action.setNetMoney(net);
                                actions.add(action);
                            }
                        }
                    }
                } else if ("SAVINGS".equalsIgnoreCase(assetClass)) {
                    BigDecimal cashTargetW = targetMap.getOrDefault("CASH", new BigDecimal("0.1000"));
                    BigDecimal cashCurrentW = valuation.getCurrentAllocations().getOrDefault("CASH", BigDecimal.ZERO);
                    // Nếu tiền mặt đang dư thừa so với tỷ trọng mục tiêu tiền mặt
                    if (cashCurrentW.compareTo(cashTargetW) > 0) {
                        BigDecimal cashSurplusMoney = totalNAV.multiply(cashCurrentW.subtract(cashTargetW)).setScale(0, RoundingMode.FLOOR);
                        BigDecimal transferMoney = deficitMoney.min(cashSurplusMoney).setScale(0, RoundingMode.FLOOR);
                        long roundedMillion = (transferMoney.longValue() / 1_000_000) * 1_000_000;
                        if (roundedMillion >= 1_000_000) {
                            BigDecimal depAmount = BigDecimal.valueOf(roundedMillion);
                            RebalancePlanDTO.RebalanceAction action = new RebalancePlanDTO.RebalanceAction(
                                    "OPEN_SAVINGS",
                                    "VND",
                                    "Tiền gửi tiết kiệm ngân hàng (Vietcombank 6T)",
                                    "SAVINGS",
                                    depAmount,
                                    depAmount,
                                    BigDecimal.ONE,
                                    depAmount,
                                    "Tỷ trọng Tiết kiệm đang thiếu " +
                                            deficitWeight.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN) +
                                            "%, trong khi tiền mặt rảnh rỗi đang dư thừa. Khuyến nghị mở sổ tiết kiệm 6 tháng để tối ưu lãi suất phi rủi ro Rf (5.5%/năm)."
                            );
                            action.setEstimatedFee(BigDecimal.ZERO);
                            action.setEstimatedTax(BigDecimal.ZERO);
                            action.setNetMoney(depAmount);
                            actions.add(action);
                        }
                    }
                }
            }
        }

        // Tổng hợp ước tính phí, thuế và dòng tiền
        BigDecimal planTotalSell = BigDecimal.ZERO;
        BigDecimal planTotalBuy = BigDecimal.ZERO;
        BigDecimal planTotalFees = BigDecimal.ZERO;
        BigDecimal planTotalTax = BigDecimal.ZERO;

        for (RebalancePlanDTO.RebalanceAction act : actions) {
            if ("SELL".equalsIgnoreCase(act.getActionType())) {
                planTotalSell = planTotalSell.add(act.getEstimatedTotalMoney());
                planTotalFees = planTotalFees.add(act.getEstimatedFee());
                planTotalTax = planTotalTax.add(act.getEstimatedTax());
            } else if ("BUY".equalsIgnoreCase(act.getActionType())) {
                planTotalBuy = planTotalBuy.add(act.getEstimatedTotalMoney());
                planTotalFees = planTotalFees.add(act.getEstimatedFee());
            } else if ("OPEN_SAVINGS".equalsIgnoreCase(act.getActionType())) {
                planTotalBuy = planTotalBuy.add(act.getEstimatedTotalMoney());
            }
        }

        plan.setTotalEstimatedSell(planTotalSell);
        plan.setTotalEstimatedBuy(planTotalBuy);
        plan.setTotalEstimatedFees(planTotalFees);
        plan.setTotalEstimatedTax(planTotalTax);
        plan.setNetCashImpact(planTotalSell.subtract(planTotalBuy).subtract(planTotalFees).subtract(planTotalTax));

        // Tóm tắt kế hoạch
        if (isDrift) {
            plan.setExecutiveSummary("Phát hiện tỷ trọng danh mục lệch " + plan.getMaxDriftPercent() +
                    "% so với mục tiêu TAA (đã điều chỉnh theo tín hiệu ML: Cổ phiếu " +
                    stockPrediction.regimeName() + " " + String.format("%.0f%%", stockPrediction.confidence() * 100) +
                    ", Vàng " + goldPrediction.regimeName() + " " + String.format("%.0f%%", goldPrediction.confidence() * 100) +
                    "). Đề xuất thực hiện các lệnh điều chỉnh lô chẵn bên dưới.");
        } else {
            plan.setExecutiveSummary("Danh mục hiện tại đang duy trì trạng thái cân bằng tốt (Độ lệch tối đa " + plan.getMaxDriftPercent() + "% < 5%). Khuyến nghị tiếp tục nắm giữ kỷ luật.");
        }

        plan.setActions(actions);
        return plan;
    }

    @Transactional
    public RebalanceExecutionResultDTO executeRebalancePlan(Long userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy người dùng ID: " + userId));

        RebalancePlanDTO plan = generateRebalancePlan(userId);
        if (plan.getActions() == null || plan.getActions().isEmpty()) {
            if (plan.isDriftDetected()) {
                throw new IllegalStateException("Độ lệch tỷ trọng chưa đủ để cấu thành lô giao dịch tối thiểu (100 cổ phiếu hoặc 1 chỉ vàng), hoặc số dư tiền mặt không đủ để thực hiện lệnh mua.");
            }
            throw new IllegalStateException("Danh mục đang ở trạng thái cân bằng tối ưu, không có hành động tái cơ cấu nào cần thực thi.");
        }

        Asset vndAsset = assetRepository.findById("VND")
                .orElseThrow(() -> new IllegalStateException("Không tìm thấy tài sản VND"));

        Account vndWallet = accountRepository.findByUserIdAndAccountCode(userId, "VND_WALLET")
                .orElseGet(() -> accountRepository.save(new Account(user, "VND_WALLET", vndAsset, BigDecimal.ZERO)));

        String txCode = "TX_REBAL_" + System.currentTimeMillis();
        Transaction transaction = new Transaction(txCode, user, "REBALANCE",
                "Tái cơ cấu danh mục tự động: điều chỉnh độ lệch " + plan.getMaxDriftPercent() + "% theo Markowitz & ONNX Regime");

        BigDecimal totalSold = BigDecimal.ZERO;
        BigDecimal totalBought = BigDecimal.ZERO;
        BigDecimal totalFees = BigDecimal.ZERO;
        BigDecimal totalTax = BigDecimal.ZERO;

        // 1. Pha 1: Thực thi các lệnh BÁN cổ phiếu / vàng (SELL)
        for (RebalancePlanDTO.RebalanceAction action : plan.getActions()) {
            if ("SELL".equalsIgnoreCase(action.getActionType())) {
                Asset asset = assetRepository.findById(action.getTicker())
                        .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy tài sản: " + action.getTicker()));

                Account assetAccount = accountRepository.findByUserId(userId).stream()
                        .filter(acc -> !acc.getAccountCode().startsWith("SAVINGS_")
                                && !"EQUITY_CAPITAL".equalsIgnoreCase(acc.getAccountCode())
                                && !"INTEREST_INCOME".equalsIgnoreCase(acc.getAccountCode())
                                && !"VND_WALLET".equalsIgnoreCase(acc.getAccountCode())
                                && acc.getAsset() != null
                                && acc.getAsset().getTicker().equalsIgnoreCase(asset.getTicker()))
                        .findFirst()
                        .orElseGet(() -> {
                            String defaultAccountCode = "ASSET_" + asset.getTicker();
                            return accountRepository.save(new Account(user, defaultAccountCode, asset, BigDecimal.ZERO));
                        });

                BigDecimal qty = action.getRoundedQuantity();
                BigDecimal price = action.getEstimatedPrice();
                BigDecimal money = qty.multiply(price).setScale(4, RoundingMode.HALF_EVEN);

                if (assetAccount.getBalance().compareTo(qty) < 0) {
                    qty = assetAccount.getBalance();
                    money = qty.multiply(price).setScale(4, RoundingMode.HALF_EVEN);
                }

                if (qty.compareTo(BigDecimal.ZERO) > 0) {
                    BigDecimal fee = money.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
                    BigDecimal tax = money.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
                    BigDecimal netProceeds = money.subtract(fee).subtract(tax);

                    assetAccount.setBalance(assetAccount.getBalance().subtract(qty));
                    vndWallet.setBalance(vndWallet.getBalance().add(netProceeds));

                    assetAccount = accountRepository.save(assetAccount);
                    vndWallet = accountRepository.save(vndWallet);

                    Entry debitEntry = new Entry(transaction, vndWallet, netProceeds);
                    Entry creditEntry = new Entry(transaction, assetAccount, qty.negate());

                    transaction.addEntry(debitEntry);
                    transaction.addEntry(creditEntry);

                    totalSold = totalSold.add(money);
                    totalFees = totalFees.add(fee);
                    totalTax = totalTax.add(tax);
                }
            }
        }
        vndWallet = accountRepository.findByUserIdAndAccountCode(userId, "VND_WALLET").orElse(vndWallet);

        // 2. Pha 2: Thực thi các lệnh TẤT TOÁN SỔ TIẾT KIỆM (SETTLE_SAVINGS) -> tiền về thẳng ví tiền mặt
        for (RebalancePlanDTO.RebalanceAction action : plan.getActions()) {
            if ("SETTLE_SAVINGS".equalsIgnoreCase(action.getActionType())) {
                try {
                    Long depositId = Long.parseLong(action.getTicker());
                    ledgerService.settleSavingsDeposit(depositId);
                    totalSold = totalSold.add(action.getEstimatedTotalMoney());
                } catch (Exception e) {
                    // Sổ có thể đã được tất toán hoặc có lỗi ngoại lệ
                }
            }
        }
        vndWallet = accountRepository.findByUserIdAndAccountCode(userId, "VND_WALLET").orElse(vndWallet);

        // 3. Pha 3: Thực thi các lệnh MUA (BUY) -> Lúc này ví VND đã có đủ tiền từ Pha 1 & 2
        for (RebalancePlanDTO.RebalanceAction action : plan.getActions()) {
            if ("BUY".equalsIgnoreCase(action.getActionType())) {
                Asset asset = assetRepository.findById(action.getTicker())
                        .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy tài sản: " + action.getTicker()));

                Account assetAccount = accountRepository.findByUserId(userId).stream()
                        .filter(acc -> !acc.getAccountCode().startsWith("SAVINGS_")
                                && !"EQUITY_CAPITAL".equalsIgnoreCase(acc.getAccountCode())
                                && !"INTEREST_INCOME".equalsIgnoreCase(acc.getAccountCode())
                                && !"VND_WALLET".equalsIgnoreCase(acc.getAccountCode())
                                && acc.getAsset() != null
                                && acc.getAsset().getTicker().equalsIgnoreCase(asset.getTicker()))
                        .findFirst()
                        .orElseGet(() -> {
                            String defaultAccountCode = "ASSET_" + asset.getTicker();
                            return accountRepository.save(new Account(user, defaultAccountCode, asset, BigDecimal.ZERO));
                        });

                BigDecimal qty = action.getRoundedQuantity();
                BigDecimal price = action.getEstimatedPrice();
                BigDecimal money = qty.multiply(price).setScale(4, RoundingMode.HALF_EVEN);
                BigDecimal fee = money.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
                BigDecimal totalRequired = money.add(fee);

                if (vndWallet.getBalance().compareTo(totalRequired) < 0) {
                    BigDecimal unitCost = price.multiply(new BigDecimal("1.001"));
                    if (vndWallet.getBalance().compareTo(unitCost) >= 0) {
                        long affordableQty = vndWallet.getBalance().divide(unitCost, 0, RoundingMode.FLOOR).longValue();
                        if ("STOCK".equalsIgnoreCase(action.getAssetClass())) {
                            affordableQty = (affordableQty / 100) * 100;
                        }
                        qty = BigDecimal.valueOf(affordableQty);
                        money = qty.multiply(price).setScale(4, RoundingMode.HALF_EVEN);
                        fee = money.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
                        totalRequired = money.add(fee);
                    } else {
                        continue;
                    }
                }

                if (qty.compareTo(BigDecimal.ZERO) > 0) {
                    vndWallet.setBalance(vndWallet.getBalance().subtract(totalRequired));
                    assetAccount.setBalance(assetAccount.getBalance().add(qty));

                    vndWallet = accountRepository.save(vndWallet);
                    assetAccount = accountRepository.save(assetAccount);

                    Entry debitEntry = new Entry(transaction, assetAccount, qty);
                    Entry creditEntry = new Entry(transaction, vndWallet, totalRequired.negate());

                    transaction.addEntry(debitEntry);
                    transaction.addEntry(creditEntry);

                    totalBought = totalBought.add(money);
                    totalFees = totalFees.add(fee);
                }
            }
        }
        vndWallet = accountRepository.findByUserIdAndAccountCode(userId, "VND_WALLET").orElse(vndWallet);

        // 4. Pha 4: Thực thi các lệnh MỞ SỔ TIẾT KIỆM (OPEN_SAVINGS) nếu tiền mặt vẫn còn dư thừa
        for (RebalancePlanDTO.RebalanceAction action : plan.getActions()) {
            if ("OPEN_SAVINGS".equalsIgnoreCase(action.getActionType())) {
                BigDecimal depMoney = action.getRoundedQuantity();
                if (vndWallet.getBalance().compareTo(depMoney) >= 0 && depMoney.compareTo(BigDecimal.ZERO) > 0) {
                    OpenSavingsRequest savReq = new OpenSavingsRequest();
                    savReq.setBankName("Vietcombank");
                    savReq.setPrincipalAmount(depMoney);
                    savReq.setInterestRate(new BigDecimal("5.5"));
                    savReq.setTermMonths(6);
                    savReq.setAutoRollover(true);
                    ledgerService.openSavingsDeposit(userId, savReq);
                    totalBought = totalBought.add(depMoney);
                    vndWallet = accountRepository.findByUserIdAndAccountCode(userId, "VND_WALLET").orElse(vndWallet);
                }
            }
        }

        if (transaction.getEntries().isEmpty() && totalBought.compareTo(BigDecimal.ZERO) == 0 && totalSold.compareTo(BigDecimal.ZERO) == 0) {
            throw new IllegalStateException("Số dư tiền mặt hoặc tài sản không đủ để thực hiện khớp lệnh tái cơ cấu.");
        }

        if (!transaction.getEntries().isEmpty()) {
            transaction = transactionRepository.save(transaction);
        }

        // Tính toán lại định giá danh mục và kế hoạch mới sau tái cơ cấu
        PortfolioValuationDTO newValuation = ledgerService.calculatePortfolioValuation(userId);
        RebalancePlanDTO newPlan = generateRebalancePlan(userId);

        RebalanceExecutionResultDTO result = new RebalanceExecutionResultDTO();
        result.setTransactionCode(txCode);
        result.setActionCount(plan.getActions().size());
        result.setTotalSoldMoney(totalSold);
        result.setTotalBoughtMoney(totalBought);
        result.setTotalFees(totalFees);
        result.setTotalTax(totalTax);
        result.setNetCashChange(totalSold.subtract(totalBought).subtract(totalFees).subtract(totalTax));
        result.setUpdatedValuation(newValuation);
        result.setUpdatedPlan(newPlan);
        result.setMessage("Đã thực thi tái cơ cấu thành công với mã giao dịch " + txCode + ". Tổng phí môi giới & thuế khấu trừ: " + totalFees.add(totalTax).setScale(0, RoundingMode.HALF_EVEN) + " ₫. Danh mục đã về vùng cân bằng tối ưu.");

        return result;
    }
}
