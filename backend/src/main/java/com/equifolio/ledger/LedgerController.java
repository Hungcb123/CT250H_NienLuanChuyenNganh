package com.equifolio.ledger;

import com.equifolio.auth.SecurityUtils;
import com.equifolio.common.ApiResponse;
import com.equifolio.optimizer.PortfolioOptimizerService;
import com.equifolio.optimizer.RebalanceExecutionResultDTO;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;

@RestController
@RequestMapping("/api/v1/ledger")
public class LedgerController {

    private final LedgerService ledgerService;
    private final PortfolioOptimizerService optimizerService;

    public LedgerController(LedgerService ledgerService, PortfolioOptimizerService optimizerService) {
        this.ledgerService = ledgerService;
        this.optimizerService = optimizerService;
    }

    @GetMapping("/accounts")
    public ResponseEntity<ApiResponse<List<Account>>> getAccounts() {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        return ResponseEntity.ok(ApiResponse.success(ledgerService.getAccountsByUserId(userId)));
    }

    @GetMapping("/transactions")
    public ResponseEntity<ApiResponse<List<TransactionDTO>>> getTransactions() {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        return ResponseEntity.ok(ApiResponse.success(ledgerService.getTransactionDTOsByUserId(userId)));
    }

    @GetMapping("/transactions/{id}/entries")
    public ResponseEntity<ApiResponse<List<Entry>>> getTransactionEntries(@PathVariable("id") Long transactionId) {
        return ResponseEntity.ok(ApiResponse.success(ledgerService.getEntriesByTransactionId(transactionId)));
    }

    @GetMapping("/portfolio-valuation")
    public ResponseEntity<ApiResponse<PortfolioValuationDTO>> getPortfolioValuation() {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        return ResponseEntity.ok(ApiResponse.success(ledgerService.calculatePortfolioValuation(userId)));
    }

    @PostMapping("/equity-injection")
    public ResponseEntity<ApiResponse<Transaction>> recordEquityInjection(@Valid @RequestBody EquityInjectionRequest request) {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        Transaction tx = ledgerService.recordEquityInjection(userId, request);
        return ResponseEntity.ok(ApiResponse.success("Khai báo tài sản ban đầu thành công", tx));
    }

    @PostMapping("/trade")
    public ResponseEntity<ApiResponse<TransactionDTO>> executeTrade(@Valid @RequestBody TradeOrderRequest request) {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        TransactionDTO dto = ledgerService.executeTrade(userId, request);
        return ResponseEntity.ok(ApiResponse.success("Khớp lệnh giao dịch thành công (ACID Post)", dto));
    }

    @GetMapping("/savings")
    public ResponseEntity<ApiResponse<List<SavingsDepositDTO>>> getSavingsDeposits() {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        return ResponseEntity.ok(ApiResponse.success(ledgerService.getSavingsDepositsByUserId(userId)));
    }

    @PostMapping("/savings")
    public ResponseEntity<ApiResponse<SavingsDepositDTO>> openSavingsDeposit(@Valid @RequestBody OpenSavingsRequest request) {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        SavingsDepositDTO dto = ledgerService.openSavingsDeposit(userId, request);
        return ResponseEntity.ok(ApiResponse.success("Mở sổ tiết kiệm thành công", dto));
    }

    @PatchMapping("/savings/{id}/rollover")
    public ResponseEntity<ApiResponse<SavingsDepositDTO>> toggleAutoRollover(@PathVariable("id") Long id,
                                                                           @RequestParam("autoRollover") Boolean autoRollover) {
        SavingsDepositDTO dto = ledgerService.toggleAutoRollover(id, autoRollover);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật chế độ tự động tái tục thành công", dto));
    }

    @PostMapping("/savings/{id}/settle")
    public ResponseEntity<ApiResponse<TransactionDTO>> settleSavingsDeposit(@PathVariable("id") Long id) {
        TransactionDTO dto = ledgerService.settleSavingsDeposit(id);
        return ResponseEntity.ok(ApiResponse.success("Tất toán sổ tiết kiệm thành công, tiền gốc và lãi đã chuyển về ví VND", dto));
    }

    @PostMapping("/rebalance/confirm")
    public ResponseEntity<ApiResponse<RebalanceExecutionResultDTO>> confirmRebalance(@RequestParam(value = "planToken", required = false) String planToken) {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        RebalanceExecutionResultDTO result = optimizerService.executeRebalancePlan(userId, planToken);
        return ResponseEntity.ok(ApiResponse.success("Xác nhận thực hiện tái cơ cấu theo kế hoạch thành công", result));
    }

    @GetMapping("/audit")
    public ResponseEntity<ApiResponse<LedgerAuditReportDTO>> getAuditReport() {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        LedgerAuditReportDTO report = ledgerService.auditLedger(userId);
        return ResponseEntity.ok(ApiResponse.success("Đối soát kiểm toán sổ cái kép hoàn tất", report));
    }

    @GetMapping("/savings/simulate")
    public ResponseEntity<ApiResponse<CompoundSimulationDTO>> simulateSavings(
            @RequestParam(name = "principal", required = false, defaultValue = "50000000") BigDecimal principal,
            @RequestParam(name = "monthlyContribution", required = false, defaultValue = "5000000") BigDecimal monthlyContribution,
            @RequestParam(name = "annualRate", required = false, defaultValue = "6.5") BigDecimal annualRate,
            @RequestParam(name = "years", required = false, defaultValue = "10") Integer years) {
        CompoundSimulationDTO dto = ledgerService.simulateCompoundGrowth(principal, monthlyContribution, annualRate, years);
        return ResponseEntity.ok(ApiResponse.success("Mô phỏng tích sản lãi kép thành công", dto));
    }

    @GetMapping("/history")
    public ResponseEntity<ApiResponse<PortfolioHistoryDTO>> getPortfolioHistory(
            @RequestParam(name = "timeframe", required = false, defaultValue = "1M") String timeframe) {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        PortfolioHistoryDTO history = ledgerService.getPortfolioHistory(userId, timeframe);
        return ResponseEntity.ok(ApiResponse.success(history));
    }

    @GetMapping("/risk-metrics")
    public ResponseEntity<ApiResponse<RiskMetricsDTO>> getRiskMetrics() {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        RiskMetricsDTO metrics = ledgerService.calculateRiskMetrics(userId);
        return ResponseEntity.ok(ApiResponse.success(metrics));
    }

    @PostMapping("/dividend")
    public ResponseEntity<ApiResponse<TransactionDTO>> recordDividend(@Valid @RequestBody DividendRequest request) {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        TransactionDTO dto = ledgerService.recordDividend(userId, request);
        return ResponseEntity.ok(ApiResponse.success("Ghi nhận cổ tức thành công", dto));
    }
}
