package com.equifolio.market;
import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.http.*;
import java.util.List;
import org.springframework.test.util.ReflectionTestUtils;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class GoldCarryForwardRegressionTest {
    @Test void dnseSyncNeverCopiesGoldPricesIntoToday() throws Exception {
        var assets=mock(AssetRepository.class);var prices=mock(MarketPriceRepository.class);
        when(assets.findAll()).thenReturn(List.of(new Asset("GOLD_SJC","Gold","GOLD")));
        var service=new DnseMarketDataService(assets,prices,new ObjectMapper());
        var http=mock(HttpClient.class);ReflectionTestUtils.setField(service,"httpClient",http);
        var response=mock(HttpResponse.class);
        when(response.statusCode()).thenReturn(503);
        doReturn(response).when(http).send(any(HttpRequest.class),any(HttpResponse.BodyHandler.class));
        service.syncAll();
        verifyNoInteractions(prices);
    }
}
