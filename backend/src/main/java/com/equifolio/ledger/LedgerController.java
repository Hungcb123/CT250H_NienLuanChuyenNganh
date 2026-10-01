package com.equifolio.ledger;

import com.equifolio.common.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/ledger")
public class LedgerController {

    private final LedgerService ledgerService;

    public LedgerController(LedgerService ledgerService) {
        this.ledgerService = ledgerService;
    }

    @GetMapping("/accounts")
    public ResponseEntity<ApiResponse<List<Account>>> getAccounts() {
        // Tạm thời lấy tài khoản Demo User ID = 1
        return ResponseEntity.ok(ApiResponse.success(ledgerService.getAccountsByUserId(1L)));
    }

    @GetMapping("/transactions")
    public ResponseEntity<ApiResponse<List<Transaction>>> getTransactions() {
        return ResponseEntity.ok(ApiResponse.success(ledgerService.getTransactionsByUserId(1L)));
    }

    @GetMapping("/transactions/{id}/entries")
    public ResponseEntity<ApiResponse<List<Entry>>> getTransactionEntries(@PathVariable("id") Long transactionId) {
        return ResponseEntity.ok(ApiResponse.success(ledgerService.getEntriesByTransactionId(transactionId)));
    }

    @GetMapping("/portfolio-valuation")
    public ResponseEntity<ApiResponse<PortfolioValuationDTO>> getPortfolioValuation() {
        return ResponseEntity.ok(ApiResponse.success(ledgerService.calculatePortfolioValuation(1L)));
    }

    @PostMapping("/equity-injection")
    public ResponseEntity<ApiResponse<Transaction>> recordEquityInjection(@Valid @RequestBody EquityInjectionRequest request) {
        Transaction tx = ledgerService.recordEquityInjection(1L, request);
        return ResponseEntity.ok(ApiResponse.success("Khai báo tài sản ban đầu thành công", tx));
    }
}
