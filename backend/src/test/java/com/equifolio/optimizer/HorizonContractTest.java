package com.equifolio.optimizer;
import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.time.LocalDate;
import java.time.ZoneId;
import static org.junit.jupiter.api.Assertions.*;
class HorizonContractTest {
    @Test void requestsSelectedHorizonAndRejectsT20UnderLongHorizon() throws Exception {
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/v1/predict", exchange->{
            String query=exchange.getRequestURI().getQuery();
            int horizon="horizon=120".equals(query)?120:20;
            String body="""
                {"status":"READY","asset":"VNINDEX","mode":"live","session":"%s",
                 "horizon_sessions":%d,"class_scores":[0.6,0.3,0.1],"net_score":-0.5,"signal":-1,
                 "score_semantics":"class_balanced_decision_scores_not_probabilities","model_id":"test"}
                """.formatted(LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh")),horizon);
            byte[] bytes=body.getBytes(java.nio.charset.StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200,bytes.length);exchange.getResponseBody().write(bytes);exchange.close();
        });
        server.start();
        try {
            var client=new NativeRegimeService("http://127.0.0.1:"+server.getAddress().getPort(),"",new ObjectMapper());
            assertTrue(client.predict(120).available());
            assertEquals("INVALID_CONTRACT",client.predict(60).status());
            assertEquals("UNSUPPORTED_HORIZON",client.predict(30).status());
        } finally { server.stop(0); }
    }
}
