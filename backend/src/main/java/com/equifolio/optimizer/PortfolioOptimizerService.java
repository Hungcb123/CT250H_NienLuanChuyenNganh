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

    public PortfolioOptimizerService(LedgerService ledgerService,
                                     PortfolioTargetRepository portfolioTargetRepository,
                                     MarketService marketService,
                                     AccountRepository accountRepository,
                                     TransactionRepository transactionRepository,
                                     UserRepository userRepository,
                                     AssetRepository assetRepository) {
        this.ledgerService = ledgerService;
        this.portfolioTargetRepository = portfolioTargetRepository;
        this.marketService = marketService;
        this.accountRepository = accountRepository;
        this.transactionRepository = transactionRepository;
        this.userRepository = userRepository;
        this.assetRepository = assetRepository;
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
                                    totalSoldEst = totalSoldEst.add(totalEst);
                                    actions.add(new RebalancePlanDTO.RebalanceAction(
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
                                    ));
                                }
                            }
                        }
                    }
                }
            }
        }

        // B. Xét các tài sản DƯỚI tỷ trọng mục tiêu -> MUA (BUY)
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
                        BigDecimal exactGoldQty = deficitMoney.divide(goldPrice, 4, RoundingMode.HALF_EVEN);
                        BigDecimal roundedGoldQty = BigDecimal.valueOf(exactGoldQty.longValue());
                        if (roundedGoldQty.compareTo(BigDecimal.ZERO) > 0) {
                            BigDecimal totalEst = roundedGoldQty.multiply(goldPrice).setScale(0, RoundingMode.HALF_EVEN);
                            actions.add(new RebalancePlanDTO.RebalanceAction(
                                    "BUY",
                                    "GOLD_SJC",
                                    "Vàng miếng SJC 999.9",
                                    "GOLD",
                                    exactGoldQty,
                                    roundedGoldQty,
                                    goldPrice,
                                    totalEst,
                                    "Tỷ trọng nhóm Vàng hiện đang thiếu " +
                                            deficitWeight.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN) +
                                            "%. Khuyến nghị mua tích lũy " + roundedGoldQty + " chỉ SJC để phòng vệ rủi ro vĩ mô."
                            ));
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
                            actions.add(new RebalancePlanDTO.RebalanceAction(
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
                            ));
                        }
                    }
                }
            }
        }

        // Tóm tắt kế hoạch
        if (isDrift) {
            plan.setExecutiveSummary("Phát hiện tỷ trọng danh mục lệch " + plan.getMaxDriftPercent() + "% so với mục tiêu SAA. Đề xuất thực hiện các lệnh điều chỉnh lô chẵn bên dưới để đưa danh mục về vùng cân bằng tối ưu.");
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
                continue;
            }

            Asset asset = assetRepository.findById(action.getTicker())
                    .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy tài sản: " + action.getTicker()));

            // Tìm tài khoản tài sản tương ứng đã có của người dùng, hoặc khởi tạo mới và lưu ngay vào DB
            Account assetAccount = accountRepository.findByUserId(userId).stream()
                    .filter(acc -> !acc.getAccountCode().startsWith("SAVINGS_")
                            && !"EQUITY_CAPITAL".equalsIgnoreCase(acc.getAccountCode())
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

            if ("SELL".equalsIgnoreCase(action.getActionType())) {
                if (assetAccount.getBalance().compareTo(qty) < 0) {
                    qty = assetAccount.getBalance();
                    money = qty.multiply(price).setScale(4, RoundingMode.HALF_EVEN);
                }

                if (qty.compareTo(BigDecimal.ZERO) > 0) {
                    assetAccount.setBalance(assetAccount.getBalance().subtract(qty));
                    vndWallet.setBalance(vndWallet.getBalance().add(money));

                    assetAccount = accountRepository.save(assetAccount);
                    vndWallet = accountRepository.save(vndWallet);

                    Entry debitEntry = new Entry(transaction, vndWallet, money);
                    Entry creditEntry = new Entry(transaction, assetAccount, qty.negate());

                    transaction.addEntry(debitEntry);
                    transaction.addEntry(creditEntry);

                    totalSold = totalSold.add(money);
                }
            } else if ("BUY".equalsIgnoreCase(action.getActionType())) {
                if (vndWallet.getBalance().compareTo(money) < 0) {
                    if (vndWallet.getBalance().compareTo(price) >= 0) {
                        long affordableQty = vndWallet.getBalance().divide(price, 0, RoundingMode.FLOOR).longValue();
                        qty = BigDecimal.valueOf(affordableQty);
                        money = qty.multiply(price).setScale(4, RoundingMode.HALF_EVEN);
                    } else {
                        continue;
                    }
                }

                if (qty.compareTo(BigDecimal.ZERO) > 0) {
                    vndWallet.setBalance(vndWallet.getBalance().subtract(money));
                    assetAccount.setBalance(assetAccount.getBalance().add(qty));

                    vndWallet = accountRepository.save(vndWallet);
                    assetAccount = accountRepository.save(assetAccount);

                    Entry debitEntry = new Entry(transaction, assetAccount, qty);
                    Entry creditEntry = new Entry(transaction, vndWallet, money.negate());

                    transaction.addEntry(debitEntry);
                    transaction.addEntry(creditEntry);

                    totalBought = totalBought.add(money);
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
        result.setNetCashChange(totalSold.subtract(totalBought));
        result.setUpdatedValuation(newValuation);
        result.setUpdatedPlan(newPlan);
        result.setMessage("Đã thực thi tái cơ cấu thành công với mã giao dịch " + txCode + ". Độ lệch danh mục đã được cân bằng lại tối ưu.");

        return result;
    }
}
