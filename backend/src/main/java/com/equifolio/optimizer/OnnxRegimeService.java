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
import java.util.List;
import java.util.Map;

/**
 * Executes sub-millisecond ML regime classification using embedded ONNX Runtime in JVM.
 * Maps to Section 5 of ML Specification (dac_ta_mo_hinh_may_hoc.md).
 */
@Service
public class OnnxRegimeService {

    private static final Logger log = LoggerFactory.getLogger(OnnxRegimeService.class);

    private final FeatureEngineeringService featureService;

    private OrtEnvironment env;

    // Stock regime model
    private OrtSession stockSession;
    private boolean stockModelLoaded = false;

    // Gold trend model
    private OrtSession goldSession;
    private boolean goldModelLoaded = false;

    public OnnxRegimeService(FeatureEngineeringService featureService) {
        this.featureService = featureService;
    }

    @PostConstruct
    public void init() {
        env = OrtEnvironment.getEnvironment();

        // Load Stock Regime Model
        stockSession = loadModel("models/stock_regime.onnx");
        stockModelLoaded = (stockSession != null);
        if (stockModelLoaded) {
            log.info("✅ Loaded ONNX Stock Regime model successfully.");
        } else {
            log.warn("⚠️ stock_regime.onnx not found. Stock inference will use heuristic fallback.");
        }

        // Load Gold Trend Model
        goldSession = loadModel("models/gold_trend.onnx");
        goldModelLoaded = (goldSession != null);
        if (goldModelLoaded) {
            log.info("✅ Loaded ONNX Gold Trend model successfully.");
        } else {
            log.warn("⚠️ gold_trend.onnx not found. Gold inference will use heuristic fallback.");
        }
    }

    private OrtSession loadModel(String classpathResource) {
        try {
            ClassPathResource resource = new ClassPathResource(classpathResource);
            if (resource.exists()) {
                try (InputStream is = resource.getInputStream()) {
                    byte[] modelBytes = is.readAllBytes();
                    return env.createSession(modelBytes, new OrtSession.SessionOptions());
                }
            }
        } catch (Exception e) {
            log.warn("Failed to load ONNX model {}: {}", classpathResource, e.getMessage());
        }
        return null;
    }

    /**
     * Classifies market regime for T+20 horizon.
     * @param features 14 technical indicators
     * @return Regime classification: -1 (Bearish), 0 (Sideway), +1 (Bullish)
     */
    public int predictRegime(float[] features) {
        if (!stockModelLoaded || stockSession == null) {
            return fallbackHeuristic(features);
        }

        try {
            float[] inputFeatures = features;
            if (inputFeatures.length < 14) {
                inputFeatures = new float[14];
                System.arraycopy(features, 0, inputFeatures, 0, features.length);
            }

            long[] shape = new long[]{1, inputFeatures.length};
            FloatBuffer buffer = FloatBuffer.wrap(inputFeatures);
            OnnxTensor tensor = OnnxTensor.createTensor(env, buffer, shape);

            try (OrtSession.Result result = stockSession.run(Collections.singletonMap("float_input", tensor))) {
                if (result != null && result.size() > 0) {
                    OnnxValue labelVal = result.get(0);
                    if (labelVal != null && labelVal.getValue() instanceof long[] labels) {
                        long classIdx = labels[0];
                        // 0 -> -1 (Bearish), 1 -> 0 (Sideway), 2 -> +1 (Bullish)
                        return (int) classIdx - 1;
                    }
                }
            }
        } catch (Exception e) {
            log.error("Error executing ONNX inference: {}. Reverting to fallback.", e.getMessage());
        }

        return fallbackHeuristic(features);
    }

    /**
     * Dự báo regime KÈM xác suất tin cậy cho Optimizer TAA.
     * Đọc output thứ 2 (probabilities) từ ONNX model.
     *
     * @param features float[] technical indicators
     * @param session  OrtSession tương ứng (stock hoặc gold)
     * @param loaded   boolean model đã load chưa
     * @return RegimePrediction(signal, confidence, name)
     */
    private RegimePrediction predictWithConfidenceInternal(float[] features, OrtSession session, boolean loaded) {
        if (!loaded || session == null || features == null) {
            return RegimePrediction.fromSignal(fallbackHeuristic(features));
        }

        try {
            float[] inputFeatures = features;
            if (inputFeatures.length < 14) {
                inputFeatures = new float[14];
                System.arraycopy(features, 0, inputFeatures, 0, features.length);
            }

            long[] shape = new long[]{1, inputFeatures.length};
            FloatBuffer buffer = FloatBuffer.wrap(inputFeatures);
            OnnxTensor tensor = OnnxTensor.createTensor(env, buffer, shape);

            try (OrtSession.Result result = session.run(Collections.singletonMap("float_input", tensor))) {
                int signal = 0;
                double confidence = 0.33;

                // Output 0: Label (long[])
                if (result.size() > 0) {
                    OnnxValue labelVal = result.get(0);
                    if (labelVal != null && labelVal.getValue() instanceof long[] labels) {
                        signal = (int) labels[0] - 1; // 0→-1, 1→0, 2→+1
                    }
                }

                // Output 1: Probabilities (List<Map<Long, Float>>)
                // LightGBM ONNX models output probabilities as the second output
                if (result.size() > 1) {
                    OnnxValue probVal = result.get(1);
                    if (probVal != null) {
                        try {
                            // LightGBM outputs [{0: p0, 1: p1, 2: p2}]
                            @SuppressWarnings("unchecked")
                            List<Map<Long, Float>> probMaps = (List<Map<Long, Float>>) probVal.getValue();
                            if (probMaps != null && !probMaps.isEmpty()) {
                                Map<Long, Float> probs = probMaps.get(0);
                                long winningClass = signal + 1; // convert back: -1→0, 0→1, +1→2
                                Float prob = probs.get(winningClass);
                                if (prob != null) {
                                    confidence = prob.doubleValue();
                                }
                            }
                        } catch (Exception e) {
                            log.debug("Could not extract probabilities, using default confidence: {}", e.getMessage());
                        }
                    }
                }

                String name = switch (signal) {
                    case 1 -> "BULLISH_UPTREND";
                    case -1 -> "BEARISH_DOWNTREND";
                    default -> "SIDEWAY_ACCUMULATION";
                };

                return new RegimePrediction(signal, confidence, name);
            }
        } catch (Exception e) {
            log.error("ONNX inference error: {}. Falling back.", e.getMessage());
        }

        return RegimePrediction.fromSignal(fallbackHeuristic(features));
    }

    /**
     * Dự báo trạng thái thị trường CỔ PHIẾU T+20 kèm confidence.
     * Dùng features tự tính từ market_prices nếu có, fallback sang features mẫu.
     */
    public RegimePrediction predictStockRegime() {
        float[] features = featureService.calculateFeatures("VNINDEX");
        if (features == null) {
            // Fallback: thử với ticker VN30 ETF hoặc dùng sample features
            features = featureService.calculateFeatures("E1VFVN30");
        }
        if (features == null) {
            log.warn("Not enough market data for stock features. Using neutral prediction.");
            return RegimePrediction.neutral();
        }
        return predictWithConfidenceInternal(features, stockSession, stockModelLoaded);
    }

    /**
     * Dự báo trạng thái thị trường VÀNG T+20 kèm confidence.
     */
    public RegimePrediction predictGoldRegime() {
        float[] features = featureService.calculateFeatures("GOLD_SJC");
        if (features == null) {
            features = featureService.calculateFeatures("GC");
        }
        if (features == null) {
            log.warn("Not enough market data for gold features. Using neutral prediction.");
            return RegimePrediction.neutral();
        }
        return predictWithConfidenceInternal(features, goldSession, goldModelLoaded);
    }

    private int fallbackHeuristic(float[] features) {
        if (features == null || features.length < 1) {
            return 0; // Default Sideway
        }
        float rsi = features[0];
        float smaRatio = features.length > 7 ? features[7] : 1.0f;

        if (rsi > 58.0f && smaRatio > 1.02f) {
            return 1; // Bullish
        } else if (rsi < 42.0f && smaRatio < 0.98f) {
            return -1; // Bearish
        }
        return 0; // Sideway
    }

    public String getLatestRegimeName() {
        RegimePrediction prediction = predictStockRegime();
        return prediction.regimeName() + " (Độ tin cậy: " +
                String.format("%.0f%%", prediction.confidence() * 100) + ")";
    }

    @PreDestroy
    public void cleanup() {
        try {
            if (stockSession != null) stockSession.close();
            if (goldSession != null) goldSession.close();
            if (env != null) env.close();
        } catch (Exception e) {
            log.error("Error closing ONNX sessions: {}", e.getMessage());
        }
    }
}
