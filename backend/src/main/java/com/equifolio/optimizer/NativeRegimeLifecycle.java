package com.equifolio.optimizer;

import jakarta.annotation.PreDestroy;
import java.net.URI;
import java.net.http.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

/** Owns a local Python worker when configured; the worker owns daily updates. */
@Component
public class NativeRegimeLifecycle {
    private static final Logger log = LoggerFactory.getLogger(NativeRegimeLifecycle.class);
    @Value("${ml.native-managed:true}") private boolean managed;
    @Value("${ml.stock-model:native}") private String model;
    @Value("${ml.native-python:python3}") private String python;
    @Value("${ml.native-script:../ml/serve_regime_shock.py}") private String script;
    @Value("${ml.native-url:http://127.0.0.1:8091}") private String url;
    @Value("${ml.native-token:}") private String token;
    @Value("${spring.datasource.url}") private String jdbcUrl;
    @Value("${spring.datasource.username}") private String username;
    @Value("${spring.datasource.password}") private String password;
    private Process child;

    @Async
    @EventListener(ApplicationReadyEvent.class)
    public synchronized void start() {
        if (!managed || !"native".equals(model) || (child != null && child.isAlive())) return;
        URI worker = URI.create(url);
        if (!Set.of("127.0.0.1", "localhost", "::1").contains(worker.getHost())) {
            log.info("Native worker is remote; start it on its host separately");
            return;
        }
        try {
            var client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
            var check = HttpRequest.newBuilder(URI.create(url.replaceAll("/+$", "") + "/health"))
                    .timeout(Duration.ofSeconds(2)).GET().build();
            if (client.send(check, HttpResponse.BodyHandlers.discarding()).statusCode() == 200) {
                log.info("Using the existing native regime worker at {}", url);
                return;
            }
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt(); return;
        } catch (Exception unavailable) { /* No worker listening yet. */ }
        try {
            Path entry = resolveScript(script);
            var builder = new ProcessBuilder(python, "-u", entry.toString());
            builder.directory(entry.getParent().getParent().toFile());
            builder.inheritIO();
            var environment = builder.environment();
            URI database = URI.create(jdbcUrl.replaceFirst("^jdbc:", ""));
            environment.put("DB_HOST", database.getHost());
            environment.put("DB_PORT", Integer.toString(database.getPort() < 0 ? 5432 : database.getPort()));
            environment.put("DB_NAME", database.getPath().substring(1));
            environment.put("DB_USER", username);
            environment.put("DB_PASSWORD", password);
            environment.put("REGIME_HOST", worker.getHost());
            environment.put("REGIME_PORT", Integer.toString(worker.getPort() < 0 ? 8091 : worker.getPort()));
            environment.put("REGIME_API_TOKEN", token);
            environment.put("REGIME_DAILY_ENABLED", "true");
            child = builder.start();
            child.onExit().thenAccept(process -> log.warn("Native regime worker stopped (exit {}). Check Python dependencies and worker logs.", process.exitValue()));
            log.info("Started native regime worker; it will catch up market data and publish daily predictions");
        } catch (Exception error) {
            log.error("Cannot start native regime worker: {}. Configure REGIME_PYTHON/REGIME_WORKER_SCRIPT or start it separately.", error.getClass().getSimpleName());
        }
    }

    static Path resolveScript(String configured) {
        for (Path candidate : List.of(Path.of(configured), Path.of("ml/serve_regime_shock.py"))) {
            if (Files.isRegularFile(candidate)) return candidate.toAbsolutePath().normalize();
        }
        throw new IllegalStateException("Native worker script not found");
    }

    @PreDestroy
    public synchronized void stop() {
        if (child != null && child.isAlive()) {
            child.descendants().forEach(ProcessHandle::destroy);
            child.destroy();
        }
    }
}
