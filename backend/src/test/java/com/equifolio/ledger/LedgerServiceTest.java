package com.equifolio.ledger;

import com.equifolio.market.Asset;
import com.equifolio.market.AssetRepository;
import com.equifolio.market.MarketService;
import com.equifolio.profile.User;
import com.equifolio.profile.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

import java.math.BigDecimal;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class LedgerServiceTest {

    @Mock
    private AccountRepository accountRepository;

    @Mock
    private TransactionRepository transactionRepository;

    @Mock
    private EntryRepository entryRepository;

    @Mock
    private AssetRepository assetRepository;

    @Mock
    private UserRepository userRepository;

    @Mock
    private MarketService marketService;

    @Mock
    private SavingsDepositRepository savingsDepositRepository;

    private LedgerService ledgerService;

    private User mockUser;
    private Asset vndAsset;
    private Asset hpgAsset;
    private Account vndAccount;
    private Account hpgAccount;
    private Account equityAccount;

    @BeforeEach
    void setUp() {
        ledgerService = new LedgerService(
                accountRepository,
                transactionRepository,
                entryRepository,
                assetRepository,
                userRepository,
                marketService,
                savingsDepositRepository
        );

        mockUser = new User();
        mockUser.setId(1L);
        mockUser.setUsername("alex_nguyen");

        vndAsset = new Asset("VND", "Tiền mặt", "CASH");
        hpgAsset = new Asset("HPG", "Hòa Phát", "STOCK");

        vndAccount = new Account(mockUser, "VND_WALLET", vndAsset, new BigDecimal("50000000"));
        vndAccount.setId(10L);

        hpgAccount = new Account(mockUser, "STOCK_HPG", hpgAsset, new BigDecimal("1000"));
        hpgAccount.setId(11L);

        equityAccount = new Account(mockUser, "EQUITY_CAPITAL", vndAsset, new BigDecimal("75000000"));
        equityAccount.setId(12L);

        when(marketService.getLatestPrice("VND")).thenReturn(BigDecimal.ONE);
        when(marketService.getLatestPrice("HPG")).thenReturn(new BigDecimal("25000"));
    }

    @Test
    @DisplayName("Kiểm toán Sổ cái (Mục 9 SRS): Xác nhận mọi bút toán cân bằng ACID và số dư đối soát khớp hoàn toàn")
    void testAuditLedger_AllInvariantsPassed() {
        Transaction tx1 = new Transaction("TX_INJECT_001", mockUser, "CAPITAL_INJECTION", "Khai báo ban đầu");
        tx1.setId(100L);

        Entry e1 = new Entry(tx1, vndAccount, new BigDecimal("50000000"));
        Entry e2 = new Entry(tx1, hpgAccount, new BigDecimal("1000"));
        Entry e3 = new Entry(tx1, equityAccount, new BigDecimal("-75000000"));

        when(transactionRepository.findByUserIdOrderByCreatedAtDesc(1L)).thenReturn(List.of(tx1));
        when(entryRepository.findByTransactionId(100L)).thenReturn(List.of(e1, e2, e3));

        when(accountRepository.findByUserId(1L)).thenReturn(List.of(vndAccount, hpgAccount, equityAccount));
        when(entryRepository.sumAmountByAccountId(10L)).thenReturn(new BigDecimal("50000000"));
        when(entryRepository.sumAmountByAccountId(11L)).thenReturn(new BigDecimal("1000"));
        when(entryRepository.sumAmountByAccountId(12L)).thenReturn(new BigDecimal("75000000")); // đối ứng

        LedgerAuditReportDTO report = ledgerService.auditLedger(1L);

        assertNotNull(report);
        assertEquals(1, report.getTotalTransactionsChecked());
        assertEquals(1, report.getBalancedTransactions());
        assertEquals(0, report.getUnbalancedTransactions());
        assertTrue(report.isAllTransactionsBalanced());
        assertEquals("ALL_ACID_INVARIANTS_PASSED", report.getAuditStatus());
    }

    @Test
    @DisplayName("Mô phỏng Lãi kép Tích sản (Mục 7.3 & 4.3 SRS): Tính chuẩn xác dòng tiền đều FV và Bội số tài sản")
    void testSimulateCompoundGrowth_CalculationCorrect() {
        BigDecimal principal = new BigDecimal("100000000"); // 100 tr gốc
        BigDecimal monthly = new BigDecimal("5000000");      // 5 tr / tháng
        BigDecimal rate = new BigDecimal("6.0");             // 6% / năm
        int years = 5;

        CompoundSimulationDTO result = ledgerService.simulateCompoundGrowth(principal, monthly, rate, years);

        assertNotNull(result);
        assertEquals(5, result.getYears());
        assertEquals(5, result.getYearlyBreakdown().size());

        // Tổng vốn góp: 100tr + (5tr * 12 * 5) = 400tr
        assertEquals(new BigDecimal("400000000"), result.getTotalContributed());

        // FV phải lớn hơn tổng vốn góp vì có lãi sinh sôi
        assertTrue(result.getFutureValue().compareTo(result.getTotalContributed()) > 0);
        assertTrue(result.getTotalInterestEarned().compareTo(BigDecimal.ZERO) > 0);
        assertTrue(result.getWealthMultiplier().compareTo(BigDecimal.ONE) > 0);

        // Năm cuối cùng có kết số bằng futureValue
        CompoundSimulationDTO.YearlyGrowthItem lastYear = result.getYearlyBreakdown().get(4);
        assertEquals(result.getFutureValue(), lastYear.getEndBalance());
    }
}
