package com.equifolio.optimizer;

import ai.onnxruntime.*;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.InputStream;
import java.nio.FloatBuffer;
import java.util.Collections;
import java.util.Optional;

/**
 * Executes sub-millisecond ML regime classification using embedded ONNX Runtime in JVM.
 * Maps to Section 5 of ML Specification (dac_ta_mo_hinh_may_hoc.md).
 */
@Service
public class OnnxRegimeService {

    private static final Logger log = LoggerFactory.getLogger(OnnxRegimeService.class);

    private OrtEnvironment env;
    private OrtSession session;
    private boolean modelLoaded = false;

    @PostConstruct
    public void init() {
        try {
            ClassPathResource modelResource = new ClassPathResource("models/stock_regime.onnx");
            if (modelResource.exists()) {
                env = OrtEnvironment.getEnvironment();
                try (InputStream is = modelResource.getInputStream()) {
                    byte[] modelBytes = is.readAllBytes();
                    session = env.createSession(modelBytes, new OrtSession.SessionOptions());
                    modelLoaded = true;
                    log.info("Loaded ONNX Market Regime model into JVM successfully. Ready for inference.");
                }
            } else {
                log.warn("ONNX model file 'models/stock_regime.onnx' not found in classpath. Using heuristic fallback.");
            }
        } catch (Exception e) {
            log.warn("Failed to initialize ONNX Runtime session: {}. Falling back to rule-based regime.", e.getMessage());
        }
    }

    /**
     * Classifies market regime for T+20 horizon.
     * @param features 9 technical indicators: RSI_14, MACD, Signal, Hist, BB_Width, BB_PctB, SMA_Ratio, ATR_Pct, ROC_20
     * @return Regime classification: -1 (Bearish), 0 (Sideway), +1 (Bullish)
     */
    public int predictRegime(float[] features) {
        if (!modelLoaded || session == null) {
            return fallbackHeuristic(features);
        }

        try {
            long[] shape = new long[]{1, features.length};
            FloatBuffer buffer = FloatBuffer.wrap(features);
            OnnxTensor tensor = OnnxTensor.createTensor(env, buffer, shape);

            try (OrtSession.Result result = session.run(Collections.singletonMap("float_input", tensor))) {
                // LightGBM ONNX outputs: label (int64) or probabilities
                Optional<OnnxValue> labelOpt = result.get(0);
                if (labelOpt.isPresent()) {
                    long[] labels = (long[]) labelOpt.get().getValue();
                    long classIdx = labels[0];
                    // 0 -> -1 (Bearish), 1 -> 0 (Sideway), 2 -> +1 (Bullish)
                    return (int) classIdx - 1;
                }
            }
        } catch (Exception e) {
            log.error("Error executing ONNX inference: {}. Reverting to fallback.", e.getMessage());
        }

        return fallbackHeuristic(features);
    }

    private int fallbackHeuristic(float[] features) {
        if (features == null || features.length < 9) {
            return 0; // Default Sideway
        }
        float rsi = features[0];
        float smaRatio = features[6];

        if (rsi > 58.0f && smaRatio > 1.02f) {
            return 1; // Bullish
        } else if (rsi < 42.0f && smaRatio < 0.98f) {
            return -1; // Bearish
        }
        return 0; // Sideway
    }

    @PreDestroy
    public void cleanup() {
        try {
            if (session != null) {
                session.close();
            }
            if (env != null) {
                env.close();
            }
        } catch (Exception e) {
            log.error("Error closing ONNX session: {}", e.getMessage());
        }
    }
}
