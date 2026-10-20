package com.equifolio.optimizer;
import com.equifolio.auth.SecurityUtils;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;
import java.util.Optional;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class AllocationPreferenceTest {
    @Test void rejectsInvalidModesAndHorizonsBeforeWriting() {
        var jdbc=mock(JdbcTemplate.class);
        var service=new AllocationPreferenceService(jdbc);
        for(var p: new AllocationPreferenceService.Preference[]{null,
            new AllocationPreferenceService.Preference("AUTO",20),
            new AllocationPreferenceService.Preference("TAA",21)})
            assertThrows(ResponseStatusException.class,()->service.save(1L,p));
        verifyNoInteractions(jdbc);
    }
    @Test void authenticatedUserOwnsPreferenceAndAnonymousCannotWrite() throws Exception {
        var service=mock(AllocationPreferenceService.class);
        var mvc=MockMvcBuilders.standaloneSetup(new AllocationPreferenceController(service)).build();
        var preference=new AllocationPreferenceService.Preference("TAA",120);
        when(service.save(42L,preference)).thenReturn(preference);
        try(var security=mockStatic(SecurityUtils.class)) {
            security.when(SecurityUtils::getCurrentUserId).thenReturn(Optional.empty());
            mvc.perform(put("/api/v1/profile/allocation-preference").contentType("application/json")
                .content("{\"mode\":\"TAA\",\"horizonSessions\":120}")).andExpect(status().isUnauthorized());
            verifyNoInteractions(service);
            security.when(SecurityUtils::getCurrentUserId).thenReturn(Optional.of(42L));
            mvc.perform(put("/api/v1/profile/allocation-preference").contentType("application/json")
                .content("{\"mode\":\"TAA\",\"horizonSessions\":120}")).andExpect(status().isOk())
                .andExpect(jsonPath("$.data.horizonSessions").value(120));
            verify(service).save(42L,preference);
        }
    }
}
