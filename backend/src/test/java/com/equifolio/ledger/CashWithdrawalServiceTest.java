package com.equifolio.ledger;

import com.equifolio.market.Asset;
import com.equifolio.profile.User;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.util.Optional;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class CashWithdrawalServiceTest {
    final AccountRepository accounts = mock(AccountRepository.class);
    final TransactionRepository transactions = mock(TransactionRepository.class);
    final CashWithdrawalService service = new CashWithdrawalService(accounts, transactions);
    final User user = new User();
    final Asset vnd = new Asset("VND", "VND", "CASH");
    final Account wallet = new Account(user, "VND_WALLET", vnd, new BigDecimal("1000"));
    final Account capital = new Account(user, "EQUITY_CAPITAL", vnd, new BigDecimal("-1000"));

    CashWithdrawalServiceTest() {
        user.setId(7L);
        when(accounts.findByUserIdAndAccountCode(7L, "VND_WALLET")).thenReturn(Optional.of(wallet));
        when(accounts.findByUserIdAndAccountCode(7L, "EQUITY_CAPITAL")).thenReturn(Optional.of(capital));
        when(transactions.save(any())).thenAnswer(inv -> inv.getArgument(0));
    }

    @Test void withdrawalReducesCashAndBalancesHistoricalEntries() {
        var tx = service.withdraw(7L, new CashWithdrawalRequest(new BigDecimal("400"), " Test "));
        assertEquals(new BigDecimal("600"), wallet.getBalance());
        assertEquals(new BigDecimal("-600"), capital.getBalance());
        assertEquals("CAPITAL_WITHDRAWAL", tx.getType());
        assertEquals(user, tx.getUser());
        assertEquals("Test", tx.getDescription());
        assertEquals(2, tx.getEntries().size());
        assertEquals(0, tx.getEntries().stream().map(Entry::getMonetaryValue).reduce(BigDecimal.ZERO, BigDecimal::add).signum());
    }
    @Test void insufficientFundsDoNotChangeAccountsOrPostTransaction() {
        assertThrows(IllegalArgumentException.class, () -> service.withdraw(7L, new CashWithdrawalRequest(new BigDecimal("1001"), null)));
        assertEquals(new BigDecimal("1000"), wallet.getBalance());
        verify(accounts, never()).save(any());
        verifyNoInteractions(transactions);
    }
    @Test void invalidAmountsAreRejectedBeforeAccessingAccounts() {
        for (BigDecimal amount : new BigDecimal[]{null, BigDecimal.ZERO, new BigDecimal("-1"), new BigDecimal("1.5")}) {
            assertThrows(IllegalArgumentException.class, () -> service.withdraw(7L, new CashWithdrawalRequest(amount, null)));
        }
        verifyNoInteractions(accounts, transactions);
    }
    @Test void fullCashBalanceCanBeWithdrawn() {
        service.withdraw(7L, new CashWithdrawalRequest(new BigDecimal("1000"), null));
        assertEquals(0, wallet.getBalance().signum());
    }
    @Test void neverUsesAnotherUsersWallet() {
        assertThrows(IllegalArgumentException.class, () -> service.withdraw(8L, new CashWithdrawalRequest(BigDecimal.ONE, null)));
        verifyNoInteractions(transactions);
        verify(accounts, never()).save(any());
    }
}
