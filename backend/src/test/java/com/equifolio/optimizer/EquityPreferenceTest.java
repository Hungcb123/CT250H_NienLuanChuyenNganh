package com.equifolio.optimizer;
import com.equifolio.auth.SecurityUtils;
import java.math.BigDecimal;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
class EquityPreferenceTest {
    @Test void invalidRatiosDoNotWrite(){
        var jdbc=mock(JdbcTemplate.class);var service=new EquityPreferenceService(jdbc);
        for(var preference:new EquityPreferenceService.Preference[]{null,
            new EquityPreferenceService.Preference("FUTURES",BigDecimal.ONE),
            new EquityPreferenceService.Preference("MIXED",BigDecimal.ONE),
            new EquityPreferenceService.Preference("ETF",new BigDecimal(".5")),
            new EquityPreferenceService.Preference("STOCKS",new BigDecimal(".1"))})
            assertThrows(ResponseStatusException.class,()->service.save(1L,preference));
        verifyNoInteractions(jdbc);
    }
    @Test void authenticatedPreferenceIsScopedToOwner() throws Exception {
        var service=mock(EquityPreferenceService.class);
        var mvc=MockMvcBuilders.standaloneSetup(new EquityPreferenceController(service)).setControllerAdvice(new com.equifolio.common.GlobalExceptionHandler()).build();
        var preference=new EquityPreferenceService.Preference("MIXED",new BigDecimal(".6"));
        when(service.save(42L,preference)).thenReturn(preference);
        try(var security=mockStatic(SecurityUtils.class)){
            security.when(SecurityUtils::getCurrentUserId).thenReturn(Optional.empty());
            mvc.perform(put("/api/v1/profile/equity-preference").contentType("application/json").content("{\"mode\":\"ETF\",\"etfWeight\":1}")).andExpect(status().isUnauthorized());
            verifyNoInteractions(service);
            security.when(SecurityUtils::getCurrentUserId).thenReturn(Optional.of(42L));
            mvc.perform(put("/api/v1/profile/equity-preference").contentType("application/json").content("{\"mode\":\"MIXED\",\"etfWeight\":0.6}")).andExpect(status().isOk()).andExpect(jsonPath("$.data.mode").value("MIXED"));
            verify(service).save(42L,preference);
            when(service.save(eq(42L),argThat(p->p!=null&&"MIXED".equals(p.mode())&&p.etfWeight().compareTo(BigDecimal.ONE)==0)))
                .thenThrow(new ResponseStatusException(org.springframework.http.HttpStatus.BAD_REQUEST,"Tỷ lệ ETF không phù hợp"));
            mvc.perform(put("/api/v1/profile/equity-preference").contentType("application/json").content("{\"mode\":\"MIXED\",\"etfWeight\":1}"))
                .andExpect(status().isBadRequest());
        }
    }
}
