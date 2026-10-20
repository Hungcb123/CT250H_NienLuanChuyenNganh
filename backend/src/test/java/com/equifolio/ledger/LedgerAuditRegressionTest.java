package com.equifolio.ledger;

import com.equifolio.market.*;
import com.equifolio.profile.*;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class LedgerAuditRegressionTest {
    @Test
    void historicalAssetsAreUnverifiedAndNeverRepriced() {
        var accounts = mock(AccountRepository.class);
        var transactions = mock(TransactionRepository.class);
        var entries = mock(EntryRepository.class);
        var market = mock(MarketService.class);
        var service = new LedgerService(accounts, transactions, entries, mock(AssetRepository.class),
                mock(UserRepository.class), market, mock(SavingsDepositRepository.class), mock(PortfolioSnapshotRepository.class));
        var user = new User();
        var stock = new Account(user, "STOCK_HPG", new Asset("HPG", "HPG", "STOCK"), BigDecimal.ONE);
        var tx = new Transaction("STOCK", user, "TRADE_BUY", "historic trade");
        tx.setId(1L);
        when(transactions.findByUserIdOrderByCreatedAtDesc(1L)).thenReturn(List.of(tx));
        when(entries.findByTransactionId(1L)).thenReturn(List.of(new Entry(tx, stock, BigDecimal.ONE)));
        var report = service.auditLedger(1L);
        assertEquals(1, report.getUnverifiedTransactions());
        assertEquals(0, report.getUnbalancedTransactions());
        assertEquals("INSUFFICIENT_HISTORICAL_DATA", report.getAuditStatus());
        assertFalse(service.getTransactionDTOsByUserId(1L).getFirst().isAuditVerifiable());
        verifyNoInteractions(market);
    }

    @Test
    void emptyTransactionsAndSmallDiscrepanciesCannotPass() {
        var accounts = mock(AccountRepository.class);
        var transactions = mock(TransactionRepository.class);
        var entries = mock(EntryRepository.class);
        var service = new LedgerService(accounts, transactions, entries, mock(AssetRepository.class),
                mock(UserRepository.class), mock(MarketService.class), mock(SavingsDepositRepository.class), mock(PortfolioSnapshotRepository.class));
        var user = new User();
        var wallet = new Account(user, "VND_WALLET", new Asset("VND", "VND", "CASH"), new BigDecimal("0.0001"));
        wallet.setId(10L);
        var empty = new Transaction("EMPTY", user, "CAPITAL_INJECTION", "empty"); empty.setId(1L);
        var broken = new Transaction("BROKEN", user, "CAPITAL_INJECTION", "broken"); broken.setId(2L);
        when(transactions.findByUserIdOrderByCreatedAtDesc(1L)).thenReturn(List.of(empty, broken));
        when(entries.findByTransactionId(2L)).thenReturn(List.of(new Entry(broken, wallet, new BigDecimal("0.0001"))));
        when(accounts.findByUserId(1L)).thenReturn(List.of(wallet));
        when(entries.sumAmountByAccountId(10L)).thenReturn(BigDecimal.ZERO);
        var report = service.auditLedger(1L);
        assertEquals(2, report.getUnbalancedTransactions());
        assertFalse(report.isAllAccountsConsistent());
        assertEquals("DISCREPANCY_DETECTED", report.getAuditStatus());
        assertFalse(service.getTransactionDTOsByUserId(1L).get(1).isAcidBalanced());
    }
}
