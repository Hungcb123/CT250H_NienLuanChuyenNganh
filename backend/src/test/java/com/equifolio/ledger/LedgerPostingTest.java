package com.equifolio.ledger;

import com.equifolio.market.*;
import com.equifolio.profile.*;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class LedgerPostingTest {
    @Test void buyAndSellRemainBalancedWithFeesAndChangedMarketPrice() {
        for (String action : List.of("BUY", "SELL")) {
            Fixture f = new Fixture();
            f.service.executeTrade(1L, new TradeOrderRequest("HPG", action, new BigDecimal("100"), new BigDecimal("25000"), "custom note"));
            Transaction tx = f.saved.getFirst();
            assertEquals(3, tx.getEntries().size());
            assertEquals(0, tx.getEntries().stream().map(Entry::getMonetaryValue).reduce(BigDecimal.ZERO, BigDecimal::add).signum());
            assertEquals(new BigDecimal(action.equals("BUY") ? "2500" : "5000"), f.accounts.get("TRADING_COSTS").getBalance());
            when(f.transactions.findByUserIdOrderByCreatedAtDesc(1L)).thenReturn(List.of(tx));
            when(f.entries.findByTransactionId(tx.getId())).thenReturn(tx.getEntries());
            when(f.accountsRepo.findByUserId(1L)).thenReturn(List.of());
            clearInvocations(f.market);
            assertTrue(f.service.auditLedger(1L).isAllTransactionsBalanced());
            var dto = f.service.getTransactionDTOsByUserId(1L).getFirst();
            assertTrue(dto.isAcidBalanced()); assertTrue(dto.isAuditVerifiable());
            verifyNoInteractions(f.market);
            when(f.accountsRepo.findByUserId(1L)).thenReturn(new ArrayList<>(f.accounts.values()));
            when(f.market.getLatestPrice("VND")).thenReturn(BigDecimal.ONE);
            when(f.market.getLatestPrice("HPG")).thenReturn(new BigDecimal("30000"));
            assertFalse(f.service.calculatePortfolioValuation(1L).getHoldings().stream().anyMatch(h -> "TRADING_COSTS".equals(h.getAccountCode())));
        }
    }

    @Test void injectionUsesEnteredValueAndCreditBalanceMatchesEntries() {
        Fixture f = new Fixture();
        EquityInjectionRequest req = new EquityInjectionRequest();
        req.setTicker("HPG"); req.setAmount(new BigDecimal("10")); req.setEntryPrice(new BigDecimal("25000"));
        Transaction tx = f.service.recordEquityInjection(1L, req);
        assertEquals(0, tx.getEntries().stream().map(Entry::getMonetaryValue).reduce(BigDecimal.ZERO, BigDecimal::add).signum());
        assertEquals(new BigDecimal("-250000.0000"), f.accounts.get("EQUITY_CAPITAL").getBalance());
    }

    @Test void stockDividendAddsQuantityWithoutInventingMonetaryIncome() {
        Fixture f = new Fixture();
        DividendRequest req = new DividendRequest(); req.setTicker("HPG"); req.setDividendType("STOCK"); req.setTotalAmount(new BigDecimal("100"));
        f.service.recordDividend(1L, req);
        assertEquals(new BigDecimal("1100"), f.accounts.get("ASSET_HPG").getBalance());
        assertEquals(0, f.saved.getFirst().getEntries().stream().map(Entry::getMonetaryValue).reduce(BigDecimal.ZERO, BigDecimal::add).signum());
    }

    static class Fixture {
        final AccountRepository accountsRepo = mock(AccountRepository.class);
        final TransactionRepository transactions = mock(TransactionRepository.class);
        final EntryRepository entries = mock(EntryRepository.class);
        final AssetRepository assets = mock(AssetRepository.class);
        final UserRepository users = mock(UserRepository.class);
        final MarketService market = mock(MarketService.class);
        final Map<String, Account> accounts = new HashMap<>();
        final List<Transaction> saved = new ArrayList<>();
        final LedgerService service = new LedgerService(accountsRepo, transactions, entries, assets, users, market, mock(SavingsDepositRepository.class), mock(PortfolioSnapshotRepository.class));
        Fixture() {
            User user = new User(); user.setId(1L);
            Asset vnd = new Asset("VND", "VND", "CASH"), stock = new Asset("HPG", "HPG", "STOCK");
            accounts.put("VND_WALLET", new Account(user, "VND_WALLET", vnd, new BigDecimal("10000000")));
            accounts.put("ASSET_HPG", new Account(user, "ASSET_HPG", stock, new BigDecimal("1000")));
            when(users.findById(1L)).thenReturn(Optional.of(user));
            when(assets.findById("VND")).thenReturn(Optional.of(vnd)); when(assets.findById("HPG")).thenReturn(Optional.of(stock));
            when(accountsRepo.findByUserIdAndAccountCode(eq(1L), anyString())).thenAnswer(inv -> Optional.ofNullable(accounts.get(inv.getArgument(1))));
            when(accountsRepo.save(any())).thenAnswer(inv -> { Account a = inv.getArgument(0); accounts.put(a.getAccountCode(), a); return a; });
            when(transactions.save(any())).thenAnswer(inv -> { Transaction t = inv.getArgument(0); t.setId((long)saved.size()+1); saved.add(t); return t; });
        }
    }
}
