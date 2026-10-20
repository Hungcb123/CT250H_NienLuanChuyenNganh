package com.equifolio.optimizer;

import com.equifolio.auth.SecurityUtils;
import com.equifolio.common.ApiResponse;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

@RestController
@RequestMapping("/api/v1/profile/allocation-preference")
public class AllocationPreferenceController {
    private final AllocationPreferenceService service;
    public AllocationPreferenceController(AllocationPreferenceService service) { this.service = service; }
    private Long userId() { return SecurityUtils.getCurrentUserId().orElseThrow(() ->
        new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Vui lòng đăng nhập")); }
    @GetMapping
    public ApiResponse<AllocationPreferenceService.Preference> get() {
        return ApiResponse.success("Chế độ phân bổ", service.get(userId()));
    }
    @PutMapping
    public ApiResponse<AllocationPreferenceService.Preference> save(@RequestBody AllocationPreferenceService.Preference preference) {
        return ApiResponse.success("Đã lưu chế độ; chưa thực hiện giao dịch", service.save(userId(), preference));
    }
}
