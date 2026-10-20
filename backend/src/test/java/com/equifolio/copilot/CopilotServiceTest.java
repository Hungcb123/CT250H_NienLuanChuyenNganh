package com.equifolio.copilot;

import com.equifolio.ledger.LedgerService;
import com.equifolio.ledger.PortfolioValuationDTO;
import com.equifolio.optimizer.OnnxRegimeService;
import com.equifolio.optimizer.PortfolioOptimizerService;
import com.equifolio.optimizer.RebalancePlanDTO;
import com.equifolio.profile.User;
import com.equifolio.profile.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.jdbc.core.JdbcTemplate;

import java.math.BigDecimal;
import java.util.Collections;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class CopilotServiceTest {

    @Mock
    private LedgerService ledgerService;

    @Mock
    private PortfolioOptimizerService optimizerService;

    @Mock
    private OnnxRegimeService onnxRegimeService;

    @Mock
    private UserRepository userRepository;

    @Mock
    private JdbcTemplate jdbcTemplate;

    private final ObjectMapper objectMapper = new ObjectMapper();

    private CopilotService copilotService;

    private User mockUser;
    private PortfolioValuationDTO mockValuation;
    private RebalancePlanDTO mockPlan;

    @BeforeEach
    void setUp() {
        copilotService = new CopilotService(
                ledgerService,
                optimizerService,
                onnxRegimeService,
                userRepository,
                jdbcTemplate,
                objectMapper
        );

        mockUser = new User();
        mockUser.setId(1L);
        mockUser.setUsername("Alex Nguyen");
        mockUser.setRiskScore(65);
        mockUser.setRiskAversionLambda(new BigDecimal("4.25"));
        mockUser.setRiskProfile("BALANCED");

        mockValuation = new PortfolioValuationDTO();
        mockValuation.setTotalNetWorth(new BigDecimal("350000000"));
        mockValuation.setCashBalance(new BigDecimal("50000000"));
        mockValuation.setStockValue(new BigDecimal("200000000"));
        mockValuation.setGoldValue(new BigDecimal("70000000"));
        mockValuation.setSavingsValue(new BigDecimal("30000000"));
        mockValuation.setCurrentAllocations(Map.of(
                "STOCK", new BigDecimal("0.5714"),
                "GOLD", new BigDecimal("0.2000"),
                "CASH_SAVINGS", new BigDecimal("0.2286")
        ));

        mockPlan = new RebalancePlanDTO();
        mockPlan.setDriftDetected(true);
        mockPlan.setMaxDriftPercent(new BigDecimal("22.14"));
        mockPlan.setExecutiveSummary("Phát hiện tỷ trọng Cổ phiếu vượt mục tiêu.");
        mockPlan.setMlPredictions(java.util.List.of(new RebalancePlanDTO.MlPredictionInfo(
                "STOCK", "test-model", 1, 0.69, "BULL_MOMENTUM", BigDecimal.ZERO)));

        when(userRepository.findById(anyLong())).thenReturn(Optional.of(mockUser));
        when(ledgerService.calculatePortfolioValuation(anyLong())).thenReturn(mockValuation);
        when(optimizerService.generateRebalancePlan(anyLong())).thenReturn(mockPlan);
        when(onnxRegimeService.getLatestRegimeName()).thenReturn("BULL_MOMENTUM");
    }

    @Test
    @DisplayName("Khi không có Google API Key, Copilot tự động chuyển sang chế độ Native Context RAG")
    void testProcessMessage_WithoutApiKey_UsesNativeContext() {
        CopilotChatResponse response = copilotService.processMessage(1L, "Tại sao nên tái cơ cấu danh mục?", null);

        assertNotNull(response);
        assertNotNull(response.getReply());
        assertTrue(response.getReply().contains("Alex Nguyen"));
        assertTrue(response.getReply().contains("NAV"));
        assertTrue(response.getReply().contains("tái cơ cấu"));
    }

    @Test
    @DisplayName("Cấu hình Runtime API Key được lưu và nhận diện chính xác")
    void testRuntimeApiKeyConfiguration() {
        assertFalse(copilotService.hasApiKey());

        copilotService.setRuntimeApiKey("AIzaSyTestMockKey123");
        assertTrue(copilotService.hasApiKey());
        assertEquals("AIzaSyTestMockKey123", copilotService.getEffectiveApiKey(null));

        // Client override takes priority
        assertEquals("ClientOverrideKey999", copilotService.getEffectiveApiKey("ClientOverrideKey999"));
    }

    @Test
    @DisplayName("Khi có lỗi gọi API Google, Copilot không ném Exception mà fallback an toàn về Native Context")
    void testProcessMessage_InvalidKeyOrNetworkError_GracefullyFallsBack() {
        // Cung cấp một key giả lập, cuộc gọi HTTP ra Google sẽ trả về 400/403/connection error
        CopilotChatResponse response = copilotService.processMessage(1L, "Tình hình thị trường hiện tại thế nào?", "AIzaFakeKeyThatCauses400");

        assertNotNull(response);
        assertNotNull(response.getReply());
        // Do fallback, câu trả lời vẫn chứa thông tin phân tích tài chính của người dùng
        assertTrue(response.getReply().contains("Alex Nguyen"));
        assertTrue(response.getReply().contains("BULL_MOMENTUM"));
    }
}
