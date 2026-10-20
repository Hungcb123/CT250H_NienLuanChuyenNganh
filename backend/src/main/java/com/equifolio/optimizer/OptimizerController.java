package com.equifolio.optimizer;

import com.equifolio.auth.SecurityUtils;
import com.equifolio.common.ApiResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestParam;

@RestController
@RequestMapping("/api/v1/optimizer")
public class OptimizerController {

    private final PortfolioOptimizerService optimizerService;

    public OptimizerController(PortfolioOptimizerService optimizerService) {
        this.optimizerService = optimizerService;
    }

    @GetMapping("/rebalance-plan")
    public ResponseEntity<ApiResponse<RebalancePlanDTO>> getRebalancePlan() {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        RebalancePlanDTO plan = optimizerService.generateRebalancePlan(userId);
        return ResponseEntity.ok(ApiResponse.success("Tạo kế hoạch tái cơ cấu danh mục thành công", plan));
    }

    @PostMapping("/rebalance/execute")
    public ResponseEntity<ApiResponse<RebalanceExecutionResultDTO>> executeRebalance(@RequestParam(value = "planToken", required = false) String planToken) {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        RebalanceExecutionResultDTO result = optimizerService.executeRebalancePlan(userId, planToken);
        return ResponseEntity.ok(ApiResponse.success("Thực thi tái cơ cấu danh mục thành công", result));
    }
}
