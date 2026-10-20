package com.equifolio.ledger;

import com.equifolio.market.*;
import com.equifolio.profile.*;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class LedgerSettlementTest {
    @Test void savingsInterestCreditsMatchSnapshotAndCashPayout() {
        var accounts = mock(AccountRepository.class); var deposits = mock(SavingsDepositRepository.class);
        var txs = mock(TransactionRepository.class); var assets = mock(AssetRepository.class);
        var user = new User(); user.setId(1L);
        var vnd = new Asset("VND", "VND", "CASH");
        var wallet = new Account(user, "VND_WALLET", vnd, BigDecimal.ZERO);
        var savings = new Account(user, "SAVINGS_TEST", vnd, new BigDecimal("1000000"));
        var income = new Account(user, "INTEREST_INCOME", vnd, BigDecimal.ZERO);
        var deposit = new SavingsDeposit(); deposit.setId(1L); deposit.setUser(user); deposit.setAccount(savings);
        deposit.setPrincipalAmount(new BigDecimal("1000000")); deposit.setInterestRate(new BigDecimal("3.65"));
        deposit.setStartDate(LocalDate.now().minusDays(10)); deposit.setMaturityDate(LocalDate.now()); deposit.setStatus("ACTIVE"); deposit.setBankName("Test");
        when(deposits.findById(1L)).thenReturn(Optional.of(deposit));
        when(assets.findById("VND")).thenReturn(Optional.of(vnd));
        when(accounts.findByUserIdAndAccountCode(1L,"VND_WALLET")).thenReturn(Optional.of(wallet));
        when(accounts.findByUserIdAndAccountCode(1L,"INTEREST_INCOME")).thenReturn(Optional.of(income));
        when(accounts.save(any())).thenAnswer(inv->inv.getArgument(0));
        when(txs.save(any())).thenAnswer(inv->{Transaction tx=inv.getArgument(0);assertEquals(0,tx.getEntries().stream().map(Entry::getMonetaryValue).reduce(BigDecimal.ZERO,BigDecimal::add).signum());tx.setId(1L);return tx;});
        var service = new LedgerService(accounts,txs,mock(EntryRepository.class),assets,mock(UserRepository.class),mock(MarketService.class),deposits,mock(PortfolioSnapshotRepository.class));
        service.settleSavingsDeposit(1L);
        assertEquals(new BigDecimal("1001000"),wallet.getBalance());
        assertEquals(new BigDecimal("-1000"),income.getBalance());
        assertEquals(BigDecimal.ZERO,savings.getBalance());
        assertEquals("SETTLED",deposit.getStatus());
    }

    @Test void cashDividendCreditsMatchSignedEntries() {
        var f = new LedgerPostingTest.Fixture();
        var req = new DividendRequest(); req.setTicker("HPG"); req.setDividendType("CASH");req.setTotalAmount(new BigDecimal("10000"));
        f.service.recordDividend(1L,req);
        assertEquals(new BigDecimal("-9500"),f.accounts.get("EQUITY_CAPITAL").getBalance());
        assertEquals(0,f.saved.getFirst().getEntries().stream().map(Entry::getMonetaryValue).reduce(BigDecimal.ZERO,BigDecimal::add).signum());
    }
}
