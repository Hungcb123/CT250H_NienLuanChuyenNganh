package com.equifolio.profile;

import com.equifolio.auth.SecurityUtils;
import com.equifolio.common.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/profile")
public class ProfileController {

    private final ProfileService profileService;

    public ProfileController(ProfileService profileService) {
        this.profileService = profileService;
    }

    @GetMapping("/me")
    public ResponseEntity<ApiResponse<User>> getCurrentUser() {
        Long userId = SecurityUtils.getCurrentUserId().orElse(null);
        if (userId == null) {
            return ResponseEntity.status(401).body(ApiResponse.error("Chưa đăng nhập"));
        }
        User user = profileService.getUserById(userId);
        return ResponseEntity.ok(ApiResponse.success("Lấy thông tin người dùng thành công", user));
    }

    @PostMapping("/risk-survey")
    public ResponseEntity<ApiResponse<RiskSurveyResponse>> submitRiskSurvey(
            @Valid @RequestBody RiskSurveyRequest request) {
        Long userId = SecurityUtils.getCurrentUserId().orElse(null);
        if (userId == null) {
            return ResponseEntity.status(401).body(ApiResponse.error("Vui lòng đăng nhập để lưu kết quả khảo sát"));
        }
        RiskSurveyResponse response = profileService.processRiskSurvey(userId, request);
        return ResponseEntity.ok(ApiResponse.success("Khảo sát khẩu vị rủi ro hoàn tất", response));
    }

    @GetMapping("/targets")
    public ResponseEntity<ApiResponse<Map<String, BigDecimal>>> getTargets() {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        Map<String, BigDecimal> targets = profileService.getTargetsByUserId(userId);
        return ResponseEntity.ok(ApiResponse.success("Lấy tỷ trọng danh mục mục tiêu thành công", targets));
    }

    @PutMapping("/targets")
    public ResponseEntity<ApiResponse<Map<String, BigDecimal>>> updateTargets(
            @Valid @RequestBody UpdateTargetsRequest request) {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        Map<String, BigDecimal> targets = profileService.updateCustomTargets(userId, request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật tỷ trọng mục tiêu SAA thành công", targets));
    }
}
