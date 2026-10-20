package com.equifolio.ledger;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.math.BigDecimal;
import java.util.UUID;

@Service
public class CashWithdrawalService {
    private final AccountRepository accounts;
    private final TransactionRepository transactions;

    public CashWithdrawalService(AccountRepository accounts, TransactionRepository transactions) {
        this.accounts = accounts;
        this.transactions = transactions;
    }

    @Transactional
    public Transaction withdraw(Long userId, CashWithdrawalRequest request) {
        BigDecimal amount = request.amount();
        if (amount == null || amount.signum() <= 0 || amount.stripTrailingZeros().scale() > 0
                || amount.compareTo(new BigDecimal("999999999999999")) > 0) {
            throw new IllegalArgumentException("Số tiền rút phải là số nguyên dương.");
        }
        Account wallet = accounts.findByUserIdAndAccountCode(userId, "VND_WALLET")
                .orElseThrow(() -> new IllegalArgumentException("Chưa có tiền mặt khả dụng để rút."));
        Account capital = accounts.findByUserIdAndAccountCode(userId, "EQUITY_CAPITAL")
                .orElseThrow(() -> new IllegalStateException("Chưa có thông tin vốn của danh mục."));
        if (wallet.getBalance().compareTo(amount) < 0) {
            throw new IllegalArgumentException("Số tiền rút vượt quá số dư tiền mặt khả dụng.");
        }
        // Account's @Version rejects concurrent writes rather than allowing an overdraft.
        wallet.setBalance(wallet.getBalance().subtract(amount));
        capital.setBalance(capital.getBalance().add(amount));
        accounts.save(wallet);
        accounts.save(capital);
        String description = request.description() == null || request.description().isBlank()
                ? "Rút tiền khỏi danh mục" : request.description().trim();
        Transaction tx = new Transaction("TX_WITHDRAW_" + UUID.randomUUID(), wallet.getUser(),
                "CAPITAL_WITHDRAWAL", description);
        tx.addEntry(new Entry(tx, wallet, amount.negate()));
        tx.addEntry(new Entry(tx, capital, amount));
        return transactions.save(tx);
    }
}
