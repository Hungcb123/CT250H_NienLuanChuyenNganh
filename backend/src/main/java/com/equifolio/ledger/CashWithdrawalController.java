package com.equifolio.ledger;

import com.equifolio.auth.SecurityUtils;
import com.equifolio.common.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/ledger")
public class CashWithdrawalController {
    private final CashWithdrawalService service;

    public CashWithdrawalController(CashWithdrawalService service) {
        this.service = service;
    }

    @PostMapping("/withdrawal")
    public ResponseEntity<ApiResponse<Transaction>> withdraw(@Valid @RequestBody CashWithdrawalRequest request) {
        var userId = SecurityUtils.getCurrentUserId();
        if (userId.isEmpty()) {
            return ResponseEntity.status(401).body(ApiResponse.error("Vui lòng đăng nhập để rút tiền."));
        }
        return ResponseEntity.ok(ApiResponse.success("Đã ghi nhận rút tiền khỏi danh mục.",
                service.withdraw(userId.get(), request)));
    }
}
