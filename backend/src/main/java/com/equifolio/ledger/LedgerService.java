package com.equifolio.ledger;

import com.equifolio.market.Asset;
import com.equifolio.market.AssetRepository;
import com.equifolio.market.MarketService;
import com.equifolio.profile.User;
import com.equifolio.profile.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.*;

@Service
public class LedgerService {

    private final AccountRepository accountRepository;
    private final TransactionRepository transactionRepository;
    private final EntryRepository entryRepository;
    private final AssetRepository assetRepository;
    private final UserRepository userRepository;
    private final MarketService marketService;
    private final SavingsDepositRepository savingsDepositRepository;

    public LedgerService(AccountRepository accountRepository,
                         TransactionRepository transactionRepository,
                         EntryRepository entryRepository,
                         AssetRepository assetRepository,
                         UserRepository userRepository,
                         MarketService marketService,
                         SavingsDepositRepository savingsDepositRepository) {
        this.accountRepository = accountRepository;
        this.transactionRepository = transactionRepository;
        this.entryRepository = entryRepository;
        this.assetRepository = assetRepository;
        this.userRepository = userRepository;
        this.marketService = marketService;
        this.savingsDepositRepository = savingsDepositRepository;
    }

    public List<Account> getAccountsByUserId(Long userId) {
        return accountRepository.findByUserId(userId);
    }

    public List<Transaction> getTransactionsByUserId(Long userId) {
        return transactionRepository.findByUserIdOrderByCreatedAtDesc(userId);
    }

    @Transactional(readOnly = true)
    public List<TransactionDTO> getTransactionDTOsByUserId(Long userId) {
        List<Transaction> txList = transactionRepository.findByUserIdOrderByCreatedAtDesc(userId);
        List<TransactionDTO> dtos = new ArrayList<>();
        for (Transaction tx : txList) {
            TransactionDTO dto = new TransactionDTO();
            dto.setId(tx.getId());
            dto.setTransactionCode(tx.getTransactionCode());
            dto.setType(tx.getType());
            dto.setStatus(tx.getStatus());
            dto.setDescription(tx.getDescription());
            dto.setCreatedAt(tx.getCreatedAt());

            List<Entry> entries = entryRepository.findByTransactionId(tx.getId());
            List<EntryDTO> entryDTOs = new ArrayList<>();
            BigDecimal totalDebit = BigDecimal.ZERO;
            BigDecimal monetarySum = BigDecimal.ZERO;

            for (Entry e : entries) {
                Account acc = e.getAccount();
                String accCode = (acc != null) ? acc.getAccountCode() : "N/A";
                String ticker = (acc != null && acc.getAsset() != null) ? acc.getAsset().getTicker() : "";
                String name = (acc != null && acc.getAsset() != null) ? acc.getAsset().getName() : "";
                BigDecimal unitPrice = ("VND".equalsIgnoreCase(ticker) || ticker.isEmpty()) ? BigDecimal.ONE : marketService.getLatestPrice(ticker);
                if (unitPrice.compareTo(BigDecimal.ZERO) <= 0) {
                    unitPrice = BigDecimal.ONE;
                }
                BigDecimal monetaryVal = e.getAmount().multiply(unitPrice);

                entryDTOs.add(new EntryDTO(e.getId(), acc != null ? acc.getId() : null, accCode, ticker, name, e.getAmount()));
                if (monetaryVal.compareTo(BigDecimal.ZERO) > 0) {
                    totalDebit = totalDebit.add(monetaryVal);
                }
                monetarySum = monetarySum.add(monetaryVal);
            }

            dto.setEntries(entryDTOs);
            dto.setTotalAmount(totalDebit.setScale(0, RoundingMode.HALF_EVEN));
            dto.setAcidBalanced(monetarySum.abs().compareTo(new BigDecimal("100.0")) < 0);
            dtos.add(dto);
        }
        return dtos;
    }

    @Transactional(readOnly = true)
    public List<SavingsDepositDTO> getSavingsDepositsByUserId(Long userId) {
        List<SavingsDeposit> deposits = savingsDepositRepository.findByUserIdOrderByCreatedAtDesc(userId);
        List<SavingsDepositDTO> dtos = new ArrayList<>();
        LocalDate today = LocalDate.now();

        for (SavingsDeposit dep : deposits) {
            SavingsDepositDTO dto = new SavingsDepositDTO();
            dto.setId(dep.getId());
            dto.setBankName(dep.getBankName());
            dto.setPrincipalAmount(dep.getPrincipalAmount());
            dto.setInterestRate(dep.getInterestRate());
            dto.setTermMonths(dep.getTermMonths());
            dto.setStartDate(dep.getStartDate());
            dto.setMaturityDate(dep.getMaturityDate());
            dto.setAutoRollover(dep.getAutoRollover());
            dto.setStatus(dep.getStatus());
            dto.setCreatedAt(dep.getCreatedAt());

            long daysElapsed = 0;
            if (dep.getStartDate() != null && today.isAfter(dep.getStartDate())) {
                daysElapsed = ChronoUnit.DAYS.between(dep.getStartDate(), today);
            }
            long totalDays = 1;
            if (dep.getStartDate() != null && dep.getMaturityDate() != null) {
                totalDays = Math.max(1, ChronoUnit.DAYS.between(dep.getStartDate(), dep.getMaturityDate()));
            }

            dto.setDaysElapsed(daysElapsed);
            dto.setTotalDays(totalDays);
            double progress = Math.min(100.0, Math.max(0.0, ((double) daysElapsed / totalDays) * 100.0));
            dto.setProgressPercent(Math.round(progress * 10.0) / 10.0);

            if ("ACTIVE".equalsIgnoreCase(dep.getStatus())) {
                BigDecimal rateFraction = dep.getInterestRate().divide(new BigDecimal("100"), 6, RoundingMode.HALF_EVEN);
                BigDecimal daysBD = BigDecimal.valueOf(daysElapsed);
                BigDecimal accrued = dep.getPrincipalAmount()
                        .multiply(rateFraction)
                        .multiply(daysBD)
                        .divide(new BigDecimal("365"), 0, RoundingMode.HALF_EVEN);
                dto.setAccruedInterest(accrued);
            } else {
                dto.setAccruedInterest(dep.getAccruedInterest());
            }

            dtos.add(dto);
        }
        return dtos;
    }

    @Transactional
    public SavingsDepositDTO openSavingsDeposit(Long userId, OpenSavingsRequest req) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy người dùng ID: " + userId));

        Account vndWallet = accountRepository.findByUserIdAndAccountCode(userId, "VND_WALLET")
                .orElseThrow(() -> new IllegalStateException("Không tìm thấy ví tiền mặt VND"));

        if (vndWallet.getBalance().compareTo(req.getPrincipalAmount()) < 0) {
            throw new IllegalArgumentException("Số dư tiền mặt VND khả dụng (" + vndWallet.getBalance().toPlainString() + " ₫) không đủ để mở sổ tiết kiệm " + req.getPrincipalAmount().toPlainString() + " ₫");
        }

        Asset vndAsset = assetRepository.findById("VND")
                .orElseThrow(() -> new IllegalStateException("Không tìm thấy tài sản tiền tệ VND"));

        String savingsAccountCode = "SAVINGS_" + req.getBankName().toUpperCase().replaceAll("[^A-Z0-9]", "") + "_" + System.currentTimeMillis();
        Account savingsAccount = new Account(user, savingsAccountCode, vndAsset, req.getPrincipalAmount());
        savingsAccount = accountRepository.save(savingsAccount);

        vndWallet.setBalance(vndWallet.getBalance().subtract(req.getPrincipalAmount()));
        accountRepository.save(vndWallet);

        String txCode = "TX_SAV_OPEN_" + System.currentTimeMillis();
        Transaction tx = new Transaction(txCode, user, "SAVINGS_DEPOSIT",
                "Mở sổ tiết kiệm mới tại " + req.getBankName() + " kỳ hạn " + req.getTermMonths() + " tháng, lãi suất " + req.getInterestRate() + "%/năm");

        Entry debitEntry = new Entry(tx, savingsAccount, req.getPrincipalAmount());
        Entry creditEntry = new Entry(tx, vndWallet, req.getPrincipalAmount().negate());
        tx.addEntry(debitEntry);
        tx.addEntry(creditEntry);
        transactionRepository.save(tx);

        LocalDate startDate = LocalDate.now();
        LocalDate maturityDate = startDate.plusMonths(req.getTermMonths());
        SavingsDeposit deposit = new SavingsDeposit();
        deposit.setUser(user);
        deposit.setAccount(savingsAccount);
        deposit.setBankName(req.getBankName());
        deposit.setPrincipalAmount(req.getPrincipalAmount());
        deposit.setInterestRate(req.getInterestRate());
        deposit.setTermMonths(req.getTermMonths());
        deposit.setStartDate(startDate);
        deposit.setMaturityDate(maturityDate);
        deposit.setAutoRollover(req.getAutoRollover() != null ? req.getAutoRollover() : true);
        deposit.setAccruedInterest(BigDecimal.ZERO);
        deposit.setStatus("ACTIVE");
        deposit = savingsDepositRepository.save(deposit);

        SavingsDepositDTO dto = new SavingsDepositDTO();
        dto.setId(deposit.getId());
        dto.setBankName(deposit.getBankName());
        dto.setPrincipalAmount(deposit.getPrincipalAmount());
        dto.setInterestRate(deposit.getInterestRate());
        dto.setTermMonths(deposit.getTermMonths());
        dto.setStartDate(startDate);
        dto.setMaturityDate(maturityDate);
        dto.setAutoRollover(deposit.getAutoRollover());
        dto.setAccruedInterest(BigDecimal.ZERO);
        dto.setDaysElapsed(0);
        dto.setTotalDays(Math.max(1, ChronoUnit.DAYS.between(startDate, maturityDate)));
        dto.setProgressPercent(0.0);
        dto.setStatus("ACTIVE");
        dto.setCreatedAt(deposit.getCreatedAt());

        return dto;
    }

    @Transactional
    public SavingsDepositDTO toggleAutoRollover(Long depositId, Boolean autoRollover) {
        SavingsDeposit deposit = savingsDepositRepository.findById(depositId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy sổ tiết kiệm ID: " + depositId));
        deposit.setAutoRollover(autoRollover);
        savingsDepositRepository.save(deposit);

        SavingsDepositDTO dto = new SavingsDepositDTO();
        dto.setId(deposit.getId());
        dto.setBankName(deposit.getBankName());
        dto.setPrincipalAmount(deposit.getPrincipalAmount());
        dto.setInterestRate(deposit.getInterestRate());
        dto.setTermMonths(deposit.getTermMonths());
        dto.setStartDate(deposit.getStartDate());
        dto.setMaturityDate(deposit.getMaturityDate());
        dto.setAutoRollover(deposit.getAutoRollover());
        dto.setStatus(deposit.getStatus());
        return dto;
    }

    @Transactional
    public TransactionDTO settleSavingsDeposit(Long depositId) {
        SavingsDeposit deposit = savingsDepositRepository.findById(depositId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy sổ tiết kiệm ID: " + depositId));

        if (!"ACTIVE".equalsIgnoreCase(deposit.getStatus())) {
            throw new IllegalStateException("Sổ tiết kiệm này đã được tất toán hoặc không còn hoạt động.");
        }

        LocalDate today = LocalDate.now();
        long daysElapsed = Math.max(0, ChronoUnit.DAYS.between(deposit.getStartDate(), today));
        BigDecimal rateFraction = deposit.getInterestRate().divide(new BigDecimal("100"), 6, RoundingMode.HALF_EVEN);
        BigDecimal daysBD = BigDecimal.valueOf(daysElapsed);
        BigDecimal accrued = deposit.getPrincipalAmount()
                .multiply(rateFraction)
                .multiply(daysBD)
                .divide(new BigDecimal("365"), 0, RoundingMode.HALF_EVEN);

        BigDecimal totalPayout = deposit.getPrincipalAmount().add(accrued);
        User user = deposit.getUser();

        Account vndWallet = accountRepository.findByUserIdAndAccountCode(user.getId(), "VND_WALLET")
                .orElseThrow(() -> new IllegalStateException("Không tìm thấy ví tiền mặt VND"));

        Account savingsAccount = deposit.getAccount();
        Asset vndAsset = assetRepository.findById("VND")
                .orElseThrow(() -> new IllegalStateException("Không tìm thấy tài sản tiền tệ VND"));

        Account equityAccount = accountRepository.findByUserIdAndAccountCode(user.getId(), "EQUITY_CAPITAL")
                .orElseGet(() -> accountRepository.save(new Account(user, "EQUITY_CAPITAL", vndAsset, BigDecimal.ZERO)));

        savingsAccount.setBalance(BigDecimal.ZERO);
        vndWallet.setBalance(vndWallet.getBalance().add(totalPayout));
        equityAccount.setBalance(equityAccount.getBalance().add(accrued));

        savingsAccount = accountRepository.save(savingsAccount);
        vndWallet = accountRepository.save(vndWallet);
        equityAccount = accountRepository.save(equityAccount);

        String txCode = "TX_SAV_SETTLE_" + System.currentTimeMillis();
        Transaction tx = new Transaction(txCode, user, "SAVINGS_SETTLE",
                "Tất toán sổ tiết kiệm " + deposit.getBankName() + ": Nhận gốc " + deposit.getPrincipalAmount().toPlainString() + " ₫ + lãi " + accrued.toPlainString() + " ₫");

        Entry debitWallet = new Entry(tx, vndWallet, totalPayout);
        Entry creditSavings = new Entry(tx, savingsAccount, deposit.getPrincipalAmount().negate());
        Entry creditIncome = new Entry(tx, equityAccount, accrued.negate());

        tx.addEntry(debitWallet);
        tx.addEntry(creditSavings);
        tx.addEntry(creditIncome);
        transactionRepository.save(tx);

        deposit.setStatus("SETTLED");
        deposit.setAccruedInterest(accrued);
        savingsDepositRepository.save(deposit);

        TransactionDTO dto = new TransactionDTO();
        dto.setId(tx.getId());
        dto.setTransactionCode(txCode);
        dto.setType("SAVINGS_SETTLE");
        dto.setStatus("POSTED");
        dto.setDescription(tx.getDescription());
        dto.setTotalAmount(totalPayout);
        dto.setAcidBalanced(true);
        return dto;
    }

    public List<Entry> getEntriesByTransactionId(Long transactionId) {
        return entryRepository.findByTransactionId(transactionId);
    }

    @Transactional
    public Transaction recordEquityInjection(Long userId, EquityInjectionRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy người dùng ID: " + userId));

        Asset asset = assetRepository.findById(request.getTicker())
                .orElseThrow(() -> new IllegalArgumentException("Tài sản không hợp lệ: " + request.getTicker()));

        Asset vndAsset = assetRepository.findById("VND")
                .orElseThrow(() -> new IllegalStateException("Không tìm thấy tài sản tiền tệ VND trong hệ thống"));

        // 1. Xác định tài khoản tài sản đích
        String accountCode = "VND".equalsIgnoreCase(asset.getTicker()) ? "VND_WALLET" : "ASSET_" + asset.getTicker();
        Account targetAccount = accountRepository.findByUserIdAndAccountCode(userId, accountCode)
                .orElseGet(() -> accountRepository.save(new Account(user, accountCode, asset, BigDecimal.ZERO)));

        // 2. Xác định tài khoản vốn đối ứng EQUITY_CAPITAL
        Account equityAccount = accountRepository.findByUserIdAndAccountCode(userId, "EQUITY_CAPITAL")
                .orElseGet(() -> accountRepository.save(new Account(user, "EQUITY_CAPITAL", vndAsset, BigDecimal.ZERO)));

        // 3. Tính toán giá trị tiền tệ VND quy đổi
        BigDecimal unitPrice = request.getEntryPrice() != null && request.getEntryPrice().compareTo(BigDecimal.ZERO) > 0
                ? request.getEntryPrice()
                : marketService.getLatestPrice(asset.getTicker());

        if (unitPrice.compareTo(BigDecimal.ZERO) <= 0) {
            unitPrice = BigDecimal.ONE;
        }

        BigDecimal monetaryValue = "VND".equalsIgnoreCase(asset.getTicker())
                ? request.getAmount()
                : request.getAmount().multiply(unitPrice).setScale(4, RoundingMode.HALF_EVEN);

        // 4. Cập nhật số dư tài khoản & persist vào DB trước khi tạo Entry
        targetAccount.setBalance(targetAccount.getBalance().add(request.getAmount()));
        targetAccount = accountRepository.save(targetAccount);

        equityAccount.setBalance(equityAccount.getBalance().add(monetaryValue));
        equityAccount = accountRepository.save(equityAccount);

        // 5. Khởi tạo Giao dịch
        String txCode = "TX_INJECT_" + System.currentTimeMillis();
        String desc = request.getDescription() != null ? request.getDescription() : "Khai báo tài sản ban đầu: " + asset.getName();
        Transaction transaction = new Transaction(txCode, user, "CAPITAL_INJECTION", desc);

        // 6. Tạo bút toán kép:
        // Ghi Nợ (Debit) tài khoản tài sản (tăng số lượng)
        Entry debitEntry = new Entry(transaction, targetAccount, request.getAmount());
        // Ghi Có (Credit) tài khoản vốn chủ sở hữu (tăng nguồn vốn tương ứng tiền VND quy đổi)
        Entry creditEntry = new Entry(transaction, equityAccount, monetaryValue.negate());

        transaction.addEntry(debitEntry);
        transaction.addEntry(creditEntry);

        return transactionRepository.save(transaction);
    }

    @Transactional
    public TransactionDTO executeTrade(Long userId, TradeOrderRequest req) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy người dùng ID: " + userId));

        String cleanTicker = req.getTicker().trim().toUpperCase();

        Asset asset = assetRepository.findById(cleanTicker)
                .orElseGet(() -> {
                    String assetClass = (cleanTicker.contains("GOLD") || cleanTicker.contains("SJC") || cleanTicker.contains("VANG"))
                            ? "GOLD" : "STOCK";
                    Asset newAsset = new Asset(cleanTicker, cleanTicker, assetClass);
                    return assetRepository.save(newAsset);
                });

        Account vndWallet = accountRepository.findByUserIdAndAccountCode(userId, "VND_WALLET")
                .orElseThrow(() -> new IllegalStateException("Không tìm thấy ví tiền mặt VND của người dùng"));

        String assetAccountCode = "ASSET_" + asset.getTicker();
        Account assetAccount = accountRepository.findByUserIdAndAccountCode(userId, assetAccountCode)
                .orElseGet(() -> accountRepository.save(new Account(user, assetAccountCode, asset, BigDecimal.ZERO)));

        BigDecimal price = req.getPrice();
        if (price == null || price.compareTo(BigDecimal.ZERO) <= 0) {
            price = marketService.getLatestPrice(asset.getTicker());
        }
        if (price.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Giá giao dịch không hợp lệ cho mã " + cleanTicker);
        }

        marketService.saveOrUpdatePrice(asset, price);

        BigDecimal qty = req.getQuantity();
        BigDecimal grossMoney = qty.multiply(price).setScale(0, RoundingMode.HALF_EVEN);
        BigDecimal fee = grossMoney.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);

        boolean isBuy = "BUY".equalsIgnoreCase(req.getActionType());

        if (isBuy) {
            BigDecimal totalRequired = grossMoney.add(fee);
            if (vndWallet.getBalance().compareTo(totalRequired) < 0) {
                throw new IllegalArgumentException("Số dư tiền mặt VND không đủ (" +
                        vndWallet.getBalance().toPlainString() + " ₫) để mua " +
                        qty.toPlainString() + " " + asset.getTicker() + " (cần " + totalRequired.toPlainString() + " ₫ bao gồm phí)");
            }

            vndWallet.setBalance(vndWallet.getBalance().subtract(totalRequired));
            assetAccount.setBalance(assetAccount.getBalance().add(qty));

            vndWallet = accountRepository.save(vndWallet);
            assetAccount = accountRepository.save(assetAccount);

            String txCode = "TX_BUY_" + System.currentTimeMillis();
            String desc = (req.getNotes() != null && !req.getNotes().isBlank())
                    ? req.getNotes()
                    : "Khớp lệnh MUA " + qty.toPlainString() + " " + asset.getTicker() + " @ " + price.toPlainString() + " ₫ (Phí: " + fee.toPlainString() + " ₫)";

            Transaction tx = new Transaction(txCode, user, "TRADE_BUY", desc);
            Entry debitAsset = new Entry(tx, assetAccount, qty);
            Entry creditVnd = new Entry(tx, vndWallet, totalRequired.negate());
            tx.addEntry(debitAsset);
            tx.addEntry(creditVnd);
            Transaction savedTx = transactionRepository.save(tx);

            TransactionDTO dto = new TransactionDTO();
            dto.setId(savedTx.getId());
            dto.setTransactionCode(txCode);
            dto.setType("TRADE_BUY");
            dto.setStatus("EXECUTED");
            dto.setDescription(desc);
            dto.setTotalAmount(totalRequired);
            dto.setAcidBalanced(true);
            return dto;
        } else {
            if (assetAccount.getBalance().compareTo(qty) < 0) {
                throw new IllegalArgumentException("Số lượng " + asset.getTicker() + " khả dụng (" +
                        assetAccount.getBalance().toPlainString() + ") không đủ để đặt lệnh bán " + qty.toPlainString());
            }

            BigDecimal tax = grossMoney.multiply(new BigDecimal("0.001")).setScale(0, RoundingMode.HALF_EVEN);
            BigDecimal netProceeds = grossMoney.subtract(fee).subtract(tax);

            assetAccount.setBalance(assetAccount.getBalance().subtract(qty));
            vndWallet.setBalance(vndWallet.getBalance().add(netProceeds));

            assetAccount = accountRepository.save(assetAccount);
            vndWallet = accountRepository.save(vndWallet);

            String txCode = "TX_SELL_" + System.currentTimeMillis();
            String desc = (req.getNotes() != null && !req.getNotes().isBlank())
                    ? req.getNotes()
                    : "Khớp lệnh BÁN " + qty.toPlainString() + " " + asset.getTicker() + " @ " + price.toPlainString() + " ₫ (Thuế & Phí: " + fee.add(tax).toPlainString() + " ₫)";

            Transaction tx = new Transaction(txCode, user, "TRADE_SELL", desc);
            Entry creditAsset = new Entry(tx, assetAccount, qty.negate());
            Entry debitVnd = new Entry(tx, vndWallet, netProceeds);
            tx.addEntry(creditAsset);
            tx.addEntry(debitVnd);
            Transaction savedTx = transactionRepository.save(tx);

            TransactionDTO dto = new TransactionDTO();
            dto.setId(savedTx.getId());
            dto.setTransactionCode(txCode);
            dto.setType("TRADE_SELL");
            dto.setStatus("EXECUTED");
            dto.setDescription(desc);
            dto.setTotalAmount(netProceeds);
            dto.setAcidBalanced(true);
            return dto;
        }
    }

    public PortfolioValuationDTO calculatePortfolioValuation(Long userId) {
        List<Account> accounts = accountRepository.findByUserId(userId);
        PortfolioValuationDTO dto = new PortfolioValuationDTO();

        BigDecimal totalNAV = BigDecimal.ZERO;
        BigDecimal cashVal = BigDecimal.ZERO;
        BigDecimal stockVal = BigDecimal.ZERO;
        BigDecimal goldVal = BigDecimal.ZERO;
        BigDecimal savingsVal = BigDecimal.ZERO;

        List<PortfolioValuationDTO.HoldingItem> holdingItems = new ArrayList<>();

        for (Account acc : accounts) {
            if ("EQUITY_CAPITAL".equalsIgnoreCase(acc.getAccountCode())) {
                continue; // Bỏ qua tài khoản đối ứng kế toán khi định giá tài sản thực tế
            }

            BigDecimal price = marketService.getLatestPrice(acc.getAsset().getTicker());
            BigDecimal marketValue = acc.getBalance().multiply(price).setScale(4, RoundingMode.HALF_EVEN);

            if (marketValue.compareTo(BigDecimal.ZERO) <= 0) {
                continue;
            }

            totalNAV = totalNAV.add(marketValue);

            String effectiveAssetClass = acc.getAsset().getAssetClass();
            if ("SAVINGS".equalsIgnoreCase(effectiveAssetClass) || acc.getAccountCode().startsWith("SAVINGS_")) {
                effectiveAssetClass = "SAVINGS";
                savingsVal = savingsVal.add(marketValue);
            } else if ("CASH".equalsIgnoreCase(effectiveAssetClass) || "VND_WALLET".equalsIgnoreCase(acc.getAccountCode())) {
                effectiveAssetClass = "CASH";
                cashVal = cashVal.add(marketValue);
            } else if ("STOCK".equalsIgnoreCase(effectiveAssetClass)) {
                stockVal = stockVal.add(marketValue);
            } else if ("GOLD".equalsIgnoreCase(effectiveAssetClass)) {
                goldVal = goldVal.add(marketValue);
            }

            holdingItems.add(new PortfolioValuationDTO.HoldingItem(
                    acc.getAccountCode(),
                    acc.getAsset().getTicker(),
                    acc.getAsset().getName(),
                    effectiveAssetClass,
                    acc.getBalance(),
                    price,
                    marketValue,
                    BigDecimal.ZERO // Sẽ tính % sau khi có totalNAV
            ));
        }

        // Tính tỷ trọng % cho từng tài sản
        if (totalNAV.compareTo(BigDecimal.ZERO) > 0) {
            for (PortfolioValuationDTO.HoldingItem item : holdingItems) {
                BigDecimal pct = item.getMarketValue().divide(totalNAV, 4, RoundingMode.HALF_EVEN);
                item.setAllocationPercent(pct);
            }

            Map<String, BigDecimal> allocations = new HashMap<>();
            allocations.put("STOCK", stockVal.divide(totalNAV, 4, RoundingMode.HALF_EVEN));
            allocations.put("GOLD", goldVal.divide(totalNAV, 4, RoundingMode.HALF_EVEN));
            allocations.put("SAVINGS", savingsVal.divide(totalNAV, 4, RoundingMode.HALF_EVEN));
            allocations.put("CASH", cashVal.divide(totalNAV, 4, RoundingMode.HALF_EVEN));
            allocations.put("CASH_SAVINGS", cashVal.add(savingsVal).divide(totalNAV, 4, RoundingMode.HALF_EVEN));
            dto.setCurrentAllocations(allocations);
        }

        dto.setTotalNetWorth(totalNAV);
        dto.setCashBalance(cashVal);
        dto.setStockValue(stockVal);
        dto.setGoldValue(goldVal);
        dto.setSavingsValue(savingsVal);
        dto.setHoldings(holdingItems);

        return dto;
    }

    @Transactional(readOnly = true)
    public LedgerAuditReportDTO auditLedger(Long userId) {
        LedgerAuditReportDTO report = new LedgerAuditReportDTO();

        // 1. Kiểm tra Bất biến 1: Tính cân bằng từng giao dịch Σ Debit - Σ Credit = 0
        List<Transaction> transactions = transactionRepository.findByUserIdOrderByCreatedAtDesc(userId);
        report.setTotalTransactionsChecked(transactions.size());

        int balancedCount = 0;
        int unbalancedCount = 0;

        for (Transaction tx : transactions) {
            List<Entry> entries = entryRepository.findByTransactionId(tx.getId());
            BigDecimal txMonetarySum = BigDecimal.ZERO;
            BigDecimal totalDebit = BigDecimal.ZERO;
            BigDecimal totalCredit = BigDecimal.ZERO;

            for (Entry entry : entries) {
                BigDecimal price = marketService.getLatestPrice(entry.getAccount().getAsset().getTicker());
                BigDecimal value = entry.getAmount().multiply(price);
                txMonetarySum = txMonetarySum.add(value);
                if (entry.getAmount().compareTo(BigDecimal.ZERO) > 0) {
                    totalDebit = totalDebit.add(value);
                } else {
                    totalCredit = totalCredit.add(value.abs());
                }
            }

            if (txMonetarySum.abs().compareTo(new BigDecimal("0.001")) <= 0) {
                balancedCount++;
            } else {
                unbalancedCount++;
                report.getUnbalancedTxList().add(new LedgerAuditReportDTO.UnbalancedTxItem(
                        tx.getTransactionCode(),
                        tx.getDescription(),
                        totalDebit.setScale(2, RoundingMode.HALF_EVEN),
                        totalCredit.setScale(2, RoundingMode.HALF_EVEN),
                        txMonetarySum.setScale(2, RoundingMode.HALF_EVEN)
                ));
            }
        }

        report.setBalancedTransactions(balancedCount);
        report.setUnbalancedTransactions(unbalancedCount);
        report.setAllTransactionsBalanced(unbalancedCount == 0);

        // 2. Kiểm tra Bất biến 2: Đối chiếu số dư Snapshot trong bảng accounts với tổng lịch sử entries
        List<Account> accounts = accountRepository.findByUserId(userId);
        boolean allAccountsConsistent = true;

        for (Account acc : accounts) {
            BigDecimal snapshotBalance = acc.getBalance();
            BigDecimal calculatedBalance = entryRepository.sumAmountByAccountId(acc.getId());
            if (calculatedBalance == null) {
                calculatedBalance = BigDecimal.ZERO;
            }

            BigDecimal discrepancy = snapshotBalance.subtract(calculatedBalance).abs();
            boolean consistent = discrepancy.compareTo(new BigDecimal("0.0001")) <= 0;

            if (!consistent) {
                allAccountsConsistent = false;
            }

            report.getAccountAuditList().add(new LedgerAuditReportDTO.AccountAuditItem(
                    acc.getAccountCode(),
                    acc.getAsset().getTicker(),
                    snapshotBalance.setScale(4, RoundingMode.HALF_EVEN),
                    calculatedBalance.setScale(4, RoundingMode.HALF_EVEN),
                    discrepancy.setScale(4, RoundingMode.HALF_EVEN),
                    consistent
            ));
        }

        report.setAllAccountsConsistent(allAccountsConsistent);

        boolean passed = report.isAllTransactionsBalanced() && allAccountsConsistent;
        report.setAuditStatus(passed ? "ALL_ACID_INVARIANTS_PASSED" : "DISCREPANCY_DETECTED");
        report.setSystemSummary(passed
                ? "Toàn bộ hệ thống sổ cái kép đạt chuẩn bảo toàn ACID 100%. Mọi bút toán cân bằng tuyệt đối (Σ Debit = Σ Credit) và số dư đối soát khớp hoàn toàn với lịch sử dòng tiền."
                : "Cảnh báo kiểm toán: Phát hiện sai lệch số học trong giao dịch hoặc số dư tài khoản.");

        return report;
    }

    public CompoundSimulationDTO simulateCompoundGrowth(BigDecimal principal,
                                                        BigDecimal monthlyContribution,
                                                        BigDecimal annualRate,
                                                        int years) {
        BigDecimal p = (principal != null && principal.compareTo(BigDecimal.ZERO) >= 0) ? principal : BigDecimal.ZERO;
        BigDecimal pmt = (monthlyContribution != null && monthlyContribution.compareTo(BigDecimal.ZERO) >= 0) ? monthlyContribution : BigDecimal.ZERO;
        BigDecimal rate = (annualRate != null && annualRate.compareTo(BigDecimal.ZERO) > 0) ? annualRate : new BigDecimal("6.5");
        int y = (years > 0 && years <= 50) ? years : 10;

        CompoundSimulationDTO dto = new CompoundSimulationDTO();
        dto.setInitialPrincipal(p.setScale(0, RoundingMode.HALF_EVEN));
        dto.setMonthlyContribution(pmt.setScale(0, RoundingMode.HALF_EVEN));
        dto.setAnnualRate(rate.setScale(2, RoundingMode.HALF_EVEN));
        dto.setYears(y);

        BigDecimal monthlyRate = rate.divide(new BigDecimal("1200"), 8, RoundingMode.HALF_EVEN); // rate / (100 * 12)
        BigDecimal currentBalance = p;
        BigDecimal cumulativeContribution = p;
        BigDecimal cumulativeInterest = BigDecimal.ZERO;

        for (int year = 1; year <= y; year++) {
            BigDecimal startOfYearBalance = currentBalance;
            BigDecimal yearlyContributed = pmt.multiply(new BigDecimal("12"));
            BigDecimal interestThisYear = BigDecimal.ZERO;

            for (int month = 1; month <= 12; month++) {
                currentBalance = currentBalance.add(pmt);
                BigDecimal monthInterest = currentBalance.multiply(monthlyRate);
                interestThisYear = interestThisYear.add(monthInterest);
                currentBalance = currentBalance.add(monthInterest);
            }

            cumulativeContribution = cumulativeContribution.add(yearlyContributed);
            cumulativeInterest = cumulativeInterest.add(interestThisYear);

            dto.getYearlyBreakdown().add(new CompoundSimulationDTO.YearlyGrowthItem(
                    year,
                    startOfYearBalance.setScale(0, RoundingMode.HALF_EVEN),
                    yearlyContributed.setScale(0, RoundingMode.HALF_EVEN),
                    cumulativeContribution.setScale(0, RoundingMode.HALF_EVEN),
                    interestThisYear.setScale(0, RoundingMode.HALF_EVEN),
                    cumulativeInterest.setScale(0, RoundingMode.HALF_EVEN),
                    currentBalance.setScale(0, RoundingMode.HALF_EVEN)
            ));
        }

        dto.setTotalContributed(cumulativeContribution.setScale(0, RoundingMode.HALF_EVEN));
        dto.setFutureValue(currentBalance.setScale(0, RoundingMode.HALF_EVEN));
        dto.setTotalInterestEarned(currentBalance.subtract(cumulativeContribution).setScale(0, RoundingMode.HALF_EVEN));

        if (cumulativeContribution.compareTo(BigDecimal.ZERO) > 0) {
            dto.setWealthMultiplier(currentBalance.divide(cumulativeContribution, 2, RoundingMode.HALF_EVEN));
        } else {
            dto.setWealthMultiplier(BigDecimal.ONE);
        }

        return dto;
    }
}
