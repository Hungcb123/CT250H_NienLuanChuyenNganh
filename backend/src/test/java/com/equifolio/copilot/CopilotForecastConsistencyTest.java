package com.equifolio.copilot;

import com.equifolio.ledger.*;
import com.equifolio.optimizer.*;
import com.equifolio.profile.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.text.NumberFormat;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.util.ReflectionTestUtils;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class CopilotForecastConsistencyTest {
    private RebalancePlanDTO plan(int signal, int horizon) {
        var forecast = new NativeRegimeForecast(true,"READY","2026-10-19","selected-native-model",
                signal < 0 ? List.of(0.7,0.2,0.1) : signal > 0 ? List.of(0.1,0.2,0.7) : List.of(0.2,0.6,0.2),
                signal * 0.6,false,"test-bundle");
        var info = new RebalancePlanDTO.MlPredictionInfo("STOCK",forecast.modelId(),signal,0,forecast.regimeName(),BigDecimal.ZERO);
        info.setNativeForecast(forecast);info.setHorizonSessions(horizon);
        var plan = new RebalancePlanDTO();plan.setHorizonSessions(horizon);plan.setMlPredictions(List.of(info));
        return plan;
    }

    @Test void selectedBearishPlanOverridesContradictoryLegacyOnnx() {
        var ledger = mock(LedgerService.class);var optimizer = mock(PortfolioOptimizerService.class);
        var oldOnnx = mock(OnnxRegimeService.class);var users = mock(UserRepository.class);
        var user = new User();user.setId(1L);user.setUsername("test");
        var valuation = new PortfolioValuationDTO();valuation.setCurrentAllocations(Map.of());
        when(users.findById(1L)).thenReturn(Optional.of(user));
        when(ledger.calculatePortfolioValuation(1L)).thenReturn(valuation);
        when(optimizer.generateRebalancePlan(1L)).thenReturn(plan(-1,60));
        when(oldOnnx.getLatestRegimeName()).thenReturn("ONNX_BULLISH_UPTREND (69%)");
        var service = new CopilotService(ledger,optimizer,oldOnnx,users,mock(JdbcTemplate.class),new ObjectMapper());
        var response = service.processMessage(1L,"Tình hình thị trường theo mô hình ML ra sao?");
        assertTrue(response.getReply().contains("Nghiêng giảm"));
        assertTrue(response.getReply().contains("T+60"));
        assertTrue(response.getReply().contains("2026-10-19"));
        assertFalse(response.getReply().contains("ONNX_BULLISH"));
        assertFalse(response.getReply().contains("69%"));
        verify(oldOnnx,never()).getLatestRegimeName();
    }

    @Test void contextPreservesEverySelectedHorizonAndDirection() {
        for(int horizon : List.of(20,60,120)) for(int signal : List.of(-1,0,1)) {
            String context = CopilotMarketContext.from(plan(signal,horizon));
            assertTrue(context.contains("T+"+horizon));
            assertTrue(context.contains(signal<0 ? "Nghiêng giảm" : signal>0 ? "Nghiêng tăng" : "Đi ngang"));
            assertTrue(context.contains("chưa hiệu chỉnh thành xác suất"));
        }
    }

    @Test void unavailableForecastDoesNotBecomeSidewaysOrAnotherModel() {
        var selected = plan(-1,120);
        selected.getMlPredictions().getFirst().setNativeForecast(NativeRegimeForecast.unavailable("STALE_SESSION"));
        String context = CopilotMarketContext.from(selected);
        assertTrue(context.contains("UNAVAILABLE"));
        assertTrue(context.contains("T+120"));
        assertFalse(context.contains("Hướng dự báo:"));
        assertTrue(CopilotMarketContext.from(new RebalancePlanDTO()).contains("UNAVAILABLE"));
    }

    @Test void geminiPromptReceivesSelectedForecastAndSeparateSavingsWeight() {
        var service = new CopilotService(mock(LedgerService.class),mock(PortfolioOptimizerService.class),
                mock(OnnxRegimeService.class),mock(UserRepository.class),mock(JdbcTemplate.class),new ObjectMapper());
        var user = new User();user.setId(1L);user.setUsername("test");
        var valuation = new PortfolioValuationDTO();valuation.setTotalNetWorth(new BigDecimal("1000"));
        valuation.setCashBalance(new BigDecimal("100"));valuation.setSavingsValue(new BigDecimal("300"));
        var plan = plan(-1,60);
        String prompt = ReflectionTestUtils.invokeMethod(service,"buildFinancialPrompt",user,valuation,plan,
                CopilotMarketContext.from(plan),List.of(),"1000 ₫","100 ₫","250 ₫","350 ₫","300 ₫",
                new BigDecimal("25"),new BigDecimal("35"),new BigDecimal("40"),"Thị trường?",NumberFormat.getInstance());
        assertNotNull(prompt);
        assertTrue(prompt.contains("Hướng dự báo: Nghiêng giảm"));
        assertTrue(prompt.contains("T+60"));
        assertTrue(prompt.contains("Tiền gửi Tiết kiệm: 300 ₫ (chiếm 30.0% NAV)"));
        assertTrue(prompt.contains("Tiền mặt khả dụng: 100 ₫ (chiếm 10.0% NAV)"));
        assertFalse(prompt.contains("69%"));
    }
}
