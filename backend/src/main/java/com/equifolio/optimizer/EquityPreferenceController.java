package com.equifolio.optimizer;
import com.equifolio.auth.SecurityUtils;
import com.equifolio.common.ApiResponse;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/profile/equity-preference")
public class EquityPreferenceController {
    private final EquityPreferenceService service;
    public EquityPreferenceController(EquityPreferenceService service){this.service=service;}
    private Long userId(){return SecurityUtils.getCurrentUserId().orElseThrow(()->new ResponseStatusException(HttpStatus.UNAUTHORIZED,"Vui lòng đăng nhập"));}
    @ExceptionHandler(ResponseStatusException.class)
    public org.springframework.http.ResponseEntity<ApiResponse<Void>> statusError(ResponseStatusException error) {
        return org.springframework.http.ResponseEntity.status(error.getStatusCode()).body(ApiResponse.error(error.getReason()));
    }
    @GetMapping public ApiResponse<EquityPreferenceService.Preference> get(){return ApiResponse.success("Cách đầu tư phần cổ phiếu",service.get(userId()));}
    @PutMapping public ApiResponse<EquityPreferenceService.Preference> save(@RequestBody EquityPreferenceService.Preference preference){
        return ApiResponse.success("Đã lưu lựa chọn; chưa thực hiện giao dịch",service.save(userId(),preference));
    }
}
