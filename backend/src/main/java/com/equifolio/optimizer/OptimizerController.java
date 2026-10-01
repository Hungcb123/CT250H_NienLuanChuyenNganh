package com.equifolio.optimizer;

import com.equifolio.common.ApiResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/optimizer")
public class OptimizerController {

    private final PortfolioOptimizerService optimizerService;

    public OptimizerController(PortfolioOptimizerService optimizerService) {
        this.optimizerService = optimizerService;
    }

    @GetMapping("/rebalance-plan")
    public ResponseEntity<ApiResponse<RebalancePlanDTO>> getRebalancePlan() {
        // Tạm thời lấy Demo User ID = 1
        RebalancePlanDTO plan = optimizerService.generateRebalancePlan(1L);
        return ResponseEntity.ok(ApiResponse.success("Tạo kế hoạch tái cơ cấu danh mục thành công", plan));
    }
}
