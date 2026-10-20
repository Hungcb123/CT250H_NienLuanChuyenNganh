package com.equifolio.optimizer;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import java.math.BigDecimal;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class AllocationChoiceTest {
    NativeRegimeForecast forecast(int signal) {
        return new NativeRegimeForecast(true,"READY","2026-10-19","test",
            signal < 0 ? List.of(.6,.3,.1) : signal > 0 ? List.of(.1,.3,.6) : List.of(.2,.6,.2),
            signal * .5,false,"hash");
    }
    @Test void selectedModeAndHorizonDriveTargetsWithoutWritingAnchorsOrTrades() {
        var f = new TaaRebalanceRegressionTest.Fixture();
        f.targets(".35",".35",".20",".10");
        f.valuation.setTotalNetWorth(BigDecimal.ZERO);
        var preferences = mock(AllocationPreferenceService.class);
        var nativeService = mock(NativeRegimeService.class);
        ReflectionTestUtils.setField(f.optimizer,"allocationPreferences",preferences);
        ReflectionTestUtils.setField(f.optimizer,"nativeRegimeService",nativeService);
        ReflectionTestUtils.setField(f.optimizer,"stockModel","native");
        for (int horizon : new int[]{20,60,120}) {
            for (int signal : new int[]{-1,0,1}) {
                when(preferences.get(1L)).thenReturn(new AllocationPreferenceService.Preference("TAA",horizon));
                when(nativeService.predict()).thenReturn(forecast(signal));
                when(nativeService.predict(horizon)).thenReturn(forecast(signal));
                var p=f.optimizer.generateRebalancePlan(1L);
                assertTrue(p.isTaaEnabled());
                assertEquals(horizon,p.getHorizonSessions());
                assertEquals(horizon,p.getMlPredictions().get(0).getHorizonSessions());
                assertEquals(0,new BigDecimal(".35").add(new BigDecimal(".10").multiply(BigDecimal.valueOf(signal))).compareTo(p.getTargetAllocations().get("STOCK")));
                assertEquals(0,new BigDecimal(".35").compareTo(p.getSaaTargets().get("STOCK")));
                assertEquals(0,new BigDecimal(".35").compareTo(p.getTargetAllocations().get("GOLD")));
                assertEquals(0,BigDecimal.ONE.compareTo(p.getTargetAllocations().get("STOCK").add(p.getTargetAllocations().get("GOLD")).add(p.getTargetAllocations().get("CASH_SAVINGS"))));
            }
        }
        when(preferences.get(1L)).thenReturn(new AllocationPreferenceService.Preference("SAA",120));
        var saa=f.optimizer.generateRebalancePlan(1L);
        assertFalse(saa.isTaaEnabled());
        assertEquals(0,new BigDecimal(".35").compareTo(saa.getTargetAllocations().get("STOCK")));
        when(preferences.get(1L)).thenReturn(new AllocationPreferenceService.Preference("TAA",120));
        when(nativeService.predict(120)).thenReturn(NativeRegimeForecast.unavailable("DAILY_UPDATE_PENDING"));
        var unavailable=f.optimizer.generateRebalancePlan(1L);
        assertEquals(0,new BigDecimal(".35").compareTo(unavailable.getTargetAllocations().get("STOCK")));
        assertNotEquals(saa.getPlanToken(),unavailable.getPlanToken());
        verify(f.targetRepo,never()).save(any());
        verifyNoInteractions(f.transactions);
    }
    @Test void directionalPolicyRespectsBoundsAndDisabledState() {
        assertEquals(BigDecimal.ZERO,DirectionalTaaPolicy.weight(new BigDecimal(".03"),forecast(-1),true));
        assertEquals(BigDecimal.ONE,DirectionalTaaPolicy.weight(new BigDecimal(".97"),forecast(1),true));
        assertEquals(new BigDecimal(".35"),DirectionalTaaPolicy.weight(new BigDecimal(".35"),forecast(-1),false));
    }
}
