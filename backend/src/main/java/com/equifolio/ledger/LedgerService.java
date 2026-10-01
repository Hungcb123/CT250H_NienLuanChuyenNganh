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
import java.util.*;

@Service
public class LedgerService {

    private final AccountRepository accountRepository;
    private final TransactionRepository transactionRepository;
    private final EntryRepository entryRepository;
    private final AssetRepository assetRepository;
    private final UserRepository userRepository;
    private final MarketService marketService;

    public LedgerService(AccountRepository accountRepository,
                         TransactionRepository transactionRepository,
                         EntryRepository entryRepository,
                         AssetRepository assetRepository,
                         UserRepository userRepository,
                         MarketService marketService) {
        this.accountRepository = accountRepository;
        this.transactionRepository = transactionRepository;
        this.entryRepository = entryRepository;
        this.assetRepository = assetRepository;
        this.userRepository = userRepository;
        this.marketService = marketService;
    }

    public List<Account> getAccountsByUserId(Long userId) {
        return accountRepository.findByUserId(userId);
    }

    public List<Transaction> getTransactionsByUserId(Long userId) {
        return transactionRepository.findByUserIdOrderByCreatedAtDesc(userId);
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
                .orElseGet(() -> new Account(user, accountCode, asset, BigDecimal.ZERO));

        // 2. Xác định tài khoản vốn đối ứng EQUITY_CAPITAL
        Account equityAccount = accountRepository.findByUserIdAndAccountCode(userId, "EQUITY_CAPITAL")
                .orElseGet(() -> new Account(user, "EQUITY_CAPITAL", vndAsset, BigDecimal.ZERO));

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

        // 4. Khởi tạo Giao dịch
        String txCode = "TX_INJECT_" + System.currentTimeMillis();
        String desc = request.getDescription() != null ? request.getDescription() : "Khai báo tài sản ban đầu: " + asset.getName();
        Transaction transaction = new Transaction(txCode, user, "CAPITAL_INJECTION", desc);

        // 5. Tạo bút toán kép:
        // Ghi Nợ (Debit) tài khoản tài sản (tăng số lượng)
        Entry debitEntry = new Entry(transaction, targetAccount, request.getAmount());
        // Ghi Có (Credit) tài khoản vốn chủ sở hữu (tăng nguồn vốn tương ứng tiền VND quy đổi)
        Entry creditEntry = new Entry(transaction, equityAccount, monetaryValue.negate());

        transaction.addEntry(debitEntry);
        transaction.addEntry(creditEntry);

        // 6. Cập nhật số dư tài khoản
        targetAccount.setBalance(targetAccount.getBalance().add(request.getAmount()));
        equityAccount.setBalance(equityAccount.getBalance().add(monetaryValue));

        accountRepository.save(targetAccount);
        accountRepository.save(equityAccount);

        return transactionRepository.save(transaction);
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

            String assetClass = acc.getAsset().getAssetClass();
            if ("CASH".equalsIgnoreCase(assetClass)) {
                cashVal = cashVal.add(marketValue);
            } else if ("STOCK".equalsIgnoreCase(assetClass)) {
                stockVal = stockVal.add(marketValue);
            } else if ("GOLD".equalsIgnoreCase(assetClass)) {
                goldVal = goldVal.add(marketValue);
            } else if ("SAVINGS".equalsIgnoreCase(assetClass) || acc.getAccountCode().startsWith("SAVINGS_")) {
                savingsVal = savingsVal.add(marketValue);
            }

            holdingItems.add(new PortfolioValuationDTO.HoldingItem(
                    acc.getAccountCode(),
                    acc.getAsset().getTicker(),
                    acc.getAsset().getName(),
                    assetClass,
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
}
