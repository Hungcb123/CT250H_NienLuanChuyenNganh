package com.equifolio.integration;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.equifolio.copilot.CopilotService;
import com.equifolio.market.DnseMarketDataService;
import com.equifolio.market.ExternalMarketSyncService;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.Cookie;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(
    properties = {
      "spring.datasource.url=${EQUIFOLIO_TEST_DB}",
      "spring.datasource.username=postgres",
      "spring.datasource.password=${EQUIFOLIO_TEST_PASSWORD:postgres}",
      "ml.taa-enabled=false"
    })
@AutoConfigureMockMvc
@EnabledIfEnvironmentVariable(named = "EQUIFOLIO_TEST_DB", matches = ".*equifolio_validation.*")
class ResearchApiTest {
  @Autowired MockMvc mvc;
  @Autowired ObjectMapper json;
  @MockBean DnseMarketDataService dnse;
  @MockBean ExternalMarketSyncService external;
  @MockBean CopilotService copilot;

  @BeforeEach
  void market() {
    when(external.getRiskFreeRate()).thenReturn(new BigDecimal("4.5"));
  }

  private Cookie register() throws Exception {
    String suffix = UUID.randomUUID().toString().substring(0, 8);
    String result =
        mvc.perform(
                post("/api/v1/auth/register")
                    .contentType("application/json")
                    .content(
                        json.writeValueAsString(
                            Map.of(
                                "username",
                                "api_" + suffix,
                                "email",
                                suffix + "@example.test",
                                "password",
                                "Validation123!"))))
            .andExpect(status().isOk())
            .andReturn()
            .getResponse()
            .getContentAsString();
    return new Cookie("access_token", json.readTree(result).path("data").path("token").asText());
  }

  @Test
  void authenticatedRoutesAndOwnership() throws Exception {
    mvc.perform(get("/api/v1/research/models")).andExpect(status().isUnauthorized());
    mvc.perform(get("/api/v1/goals")).andExpect(status().isUnauthorized());
    mvc.perform(get("/api/v1/knowledge/status")).andExpect(status().isUnauthorized());
    Cookie alice = register(), bob = register();
    mvc.perform(get("/api/v1/research/models").cookie(alice))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.models.taaEnabled").value(false))
        .andExpect(jsonPath("$.data.goldPrediction.signal").value(0));
    mvc.perform(get("/api/v1/research/evaluation").cookie(alice))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.folds.length()").value(4));
    mvc.perform(get("/api/v1/research/performance").cookie(alice))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.available").value(false));
    mvc.perform(
            get("/api/v1/research/optimize")
                .param("tickers", "FPT,HPG")
                .param("lambda", "11")
                .cookie(alice))
        .andExpect(status().isBadRequest());
    Map<String, Object> goal =
        Map.of(
            "title",
            "Học phí",
            "targetAmount",
            1200,
            "allocatedAmount",
            0,
            "monthlyContribution",
            100,
            "annualRate",
            0,
            "targetDate",
            LocalDate.now().plusYears(1).toString(),
            "version",
            0);
    var saved =
        mvc.perform(
                post("/api/v1/goals")
                    .cookie(alice)
                    .contentType("application/json")
                    .content(json.writeValueAsString(goal)))
            .andExpect(status().isOk())
            .andReturn();
    long id = json.readTree(saved.getResponse().getContentAsString()).path("data").asLong();
    mvc.perform(
            put("/api/v1/goals/" + id)
                .cookie(bob)
                .contentType("application/json")
                .content(json.writeValueAsString(goal)))
        .andExpect(status().isConflict());
    mvc.perform(get("/api/v1/goals").cookie(bob))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.length()").value(0));
    String privateToken = "private" + UUID.randomUUID().toString().replace("-", "");
    mvc.perform(
            post("/api/v1/knowledge/documents")
                .cookie(alice)
                .contentType("application/json")
                .content(
                    json.writeValueAsString(
                        Map.of(
                            "title",
                            "Tài liệu riêng",
                            "source",
                            "api-test",
                            "content",
                            privateToken))))
        .andExpect(status().isOk());
    mvc.perform(get("/api/v1/knowledge/search").param("query", privateToken).cookie(bob))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.length()").value(0));
    mvc.perform(get("/api/v1/knowledge/search").param("query", privateToken).cookie(alice))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.data.length()").value(1));
  }
}
