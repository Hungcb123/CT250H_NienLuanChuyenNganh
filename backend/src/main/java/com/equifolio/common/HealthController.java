package com.equifolio.common;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/health")
public class HealthController {

    @GetMapping
    public ResponseEntity<ApiResponse<Map<String, Object>>> healthCheck() {
        Map<String, Object> status = new HashMap<>();
        status.put("app", "EquiFolio Backend");
        status.put("status", "UP");
        status.put("version", "1.0.0");
        status.put("javaVersion", System.getProperty("java.version"));
        return ResponseEntity.ok(ApiResponse.success("Hệ thống hoạt động bình thường", status));
    }
}
