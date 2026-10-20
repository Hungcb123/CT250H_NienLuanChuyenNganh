package com.equifolio.goals;

import com.equifolio.auth.SecurityUtils;
import com.equifolio.common.ApiResponse;
import jakarta.validation.Valid;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/goals")
public class GoalController {
  private final GoalService service;

  public GoalController(GoalService service) {
    this.service = service;
  }

  private Long user() {
    return SecurityUtils.getCurrentUserIdOrDefault(null);
  }

  @GetMapping
  public ApiResponse<List<Map<String, Object>>> list() {
    return ApiResponse.success("Mục tiêu tích lũy", service.list(user()));
  }

  @PostMapping
  public ApiResponse<Long> create(@Valid @RequestBody GoalService.GoalInput g) {
    return ApiResponse.success("Đã lưu mục tiêu", service.save(user(), null, g));
  }

  @PutMapping("/{id}")
  public ApiResponse<Long> update(
      @PathVariable Long id, @Valid @RequestBody GoalService.GoalInput g) {
    return ApiResponse.success("Đã cập nhật", service.save(user(), id, g));
  }

  @DeleteMapping("/{id}")
  public ApiResponse<Void> delete(@PathVariable Long id) {
    service.delete(user(), id);
    return ApiResponse.success("Đã xóa", null);
  }
}
