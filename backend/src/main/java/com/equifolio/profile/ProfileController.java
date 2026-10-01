package com.equifolio.profile;

import com.equifolio.common.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/profile")
public class ProfileController {

    private final ProfileService profileService;

    public ProfileController(ProfileService profileService) {
        this.profileService = profileService;
    }

    @GetMapping("/me")
    public ResponseEntity<ApiResponse<User>> getCurrentUser() {
        User user = profileService.getOrCreateDemoUser();
        return ResponseEntity.ok(ApiResponse.success("Lấy thông tin người dùng thành công", user));
    }

    @PostMapping("/risk-survey")
    public ResponseEntity<ApiResponse<RiskSurveyResponse>> submitRiskSurvey(
            @Valid @RequestBody RiskSurveyRequest request) {
        // Tạm thời sử dụng Demo User ID = 1
        RiskSurveyResponse response = profileService.processRiskSurvey(1L, request);
        return ResponseEntity.ok(ApiResponse.success("Khảo sát khẩu vị rủi ro hoàn tất", response));
    }
}
