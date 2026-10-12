package com.equifolio.copilot;

import com.equifolio.auth.SecurityUtils;
import com.equifolio.common.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/copilot")
public class CopilotController {

    private final CopilotService copilotService;

    public CopilotController(CopilotService copilotService) {
        this.copilotService = copilotService;
    }

    @PostMapping("/chat")
    public ResponseEntity<ApiResponse<CopilotChatResponse>> chat(@Valid @RequestBody CopilotChatRequest request) {
        Long userId = SecurityUtils.getCurrentUserIdOrDefault(1L);
        CopilotChatResponse response = copilotService.processMessage(userId, request.getMessage(), request.getApiKey());
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @GetMapping("/status")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getStatus() {
        Map<String, Object> status = Map.of(
                "hasApiKey", copilotService.hasApiKey(),
                "model", copilotService.getModelName(),
                "provider", "Google Gemini"
        );
        return ResponseEntity.ok(ApiResponse.success(status));
    }

    @PostMapping("/key")
    public ResponseEntity<ApiResponse<Map<String, Object>>> updateApiKey(@RequestBody Map<String, String> payload) {
        String apiKey = payload != null ? payload.get("apiKey") : null;
        copilotService.setRuntimeApiKey(apiKey);
        Map<String, Object> result = Map.of(
                "saved", true,
                "hasApiKey", copilotService.hasApiKey(),
                "model", copilotService.getModelName()
        );
        return ResponseEntity.ok(ApiResponse.success("Đã cập nhật Google Gemini API Key thành công", result));
    }
}
