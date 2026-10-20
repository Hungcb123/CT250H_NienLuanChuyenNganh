package com.equifolio.copilot;

import com.equifolio.auth.SecurityUtils;
import com.equifolio.common.ApiResponse;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/knowledge")
public class KnowledgeController {
  private final KnowledgeService service;

  public KnowledgeController(KnowledgeService service) {
    this.service = service;
  }

  @GetMapping("/status")
  public ApiResponse<Map<String, Object>> status() {
    return ApiResponse.success("Trạng thái truy xuất", service.status());
  }

  @PostMapping("/documents")
  public ApiResponse<Integer> ingest(@RequestBody KnowledgeService.Document document) {
    return ApiResponse.success(
        "Đã nạp các đoạn tài liệu",
        service.ingest(SecurityUtils.getCurrentUserIdOrDefault(null), document));
  }

  @GetMapping("/search")
  public ApiResponse<List<KnowledgeService.Source>> search(@RequestParam String query) {
    return ApiResponse.success(
        "Nguồn tham khảo", service.search(SecurityUtils.getCurrentUserIdOrDefault(null), query));
  }
}
