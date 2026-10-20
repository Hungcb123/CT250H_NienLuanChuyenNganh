package com.equifolio.optimizer;

import com.equifolio.common.ApiResponse;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/research/native-regime")
public class NativeRegimeController {
  private final NativeRegimeService service;
  public NativeRegimeController(NativeRegimeService service) { this.service = service; }

  @PostMapping("/prediction")
  public ApiResponse<NativeRegimeForecast> prediction(@RequestParam(defaultValue = "20") int horizon) {
    if (!java.util.Set.of(20,60,120).contains(horizon))
      throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.BAD_REQUEST, "Kỳ hạn phải là 20, 60 hoặc 120 phiên");
    return ApiResponse.success("Dự báo VNINDEX T+" + horizon + "; score chưa hiệu chỉnh thành xác suất", horizon == 20 ? service.predict() : service.predict(horizon));
  }
}
