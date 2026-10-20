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

    @org.springframework.beans.factory.annotation.Value("${ml.taa-enabled:false}")
    private boolean taaEnabled;

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
            log.warn("⚠️ stock_regime.onnx not found. Stock inference will preserve SAA.");
        }

        // Load Gold Trend Model
        goldSession = loadModel("models/gold_trend.onnx");
        goldModelLoaded = (goldSession != null);
        if (goldModelLoaded) {
            log.info("✅ Loaded ONNX Gold Trend model successfully.");
        } else {
            log.warn("⚠️ gold_trend.onnx not found. Gold inference will preserve SAA.");
        }
    }

    private OrtSession loadModel(String classpathResource) {
        try {
            ClassPathResource resource = new ClassPathResource(classpathResource);
            if (resource.exists()) {
                try (InputStream is = resource.getInputStream()) {
                    byte[] modelBytes = is.readAllBytes();
                    try (OrtSession.SessionOptions options = new OrtSession.SessionOptions()) {
                        return env.createSession(modelBytes, options);
                    }
                }
            }
        } catch (Exception e) {
            log.warn("Failed to load ONNX model {}: {}", classpathResource, e.getMessage());
        }
        return null;
    }

    /**
     * Classifies market regime for T+20 horizon.
     * @param features 12 close-v1 indicators
     * @return Regime classification: -1 (Bearish), 0 (Sideway), +1 (Bullish)
     */
    public int predictRegime(float[] features) {
        return predictWithConfidenceInternal(features, stockSession, stockModelLoaded).signal();
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
        if (!loaded || session == null || features == null) return unavailable("MODEL_OR_DATA_UNAVAILABLE");
        try {
            var metadata = session.getMetadata().getCustomMetadata();
            if (!CloseFeatures.VERSION.equals(metadata.get("feature_version")) ||
                !CloseFeatures.NAMES.equals(metadata.get("features")) || features.length != 12)
                return unavailable("FEATURE_SCHEMA_MISMATCH");
            String inputName = session.getInputNames().iterator().next();
            var info = (TensorInfo) session.getInputInfo().get(inputName).getInfo();
            if (info.getShape()[1] != features.length) return unavailable("INPUT_SHAPE_MISMATCH");
            for (float f : features) if (!Float.isFinite(f)) return unavailable("INVALID_FEATURES");
            try (OnnxTensor tensor = OnnxTensor.createTensor(env, FloatBuffer.wrap(features), new long[]{1, features.length});
                 OrtSession.Result result = session.run(Collections.singletonMap(inputName, tensor))) {
                long label = ((long[])result.get(0).getValue())[0];
                if (label < 0 || label > 2 || result.size() < 2) return unavailable("INVALID_OUTPUT");
                Object value = result.get(1).getValue();
                double confidence;
                if (value instanceof List<?> rows && !rows.isEmpty()) {
                    Object row = rows.get(0);
                    if (row instanceof OnnxMap onnxMap) row = onnxMap.getValue();
                    if (!(row instanceof Map<?,?> probs) || !(probs.get(label) instanceof Number probability))
                        return unavailable("PROBABILITIES_UNAVAILABLE");
                    confidence = probability.doubleValue();
                } else if (value instanceof float[][] probs) confidence = probs[0][(int)label];
                else return unavailable("PROBABILITIES_UNAVAILABLE");
                if (!Double.isFinite(confidence) || confidence < 0 || confidence > 1) return unavailable("INVALID_CONFIDENCE");
                if (confidence < 0.55) return unavailable("LOW_CONFIDENCE");
                int signal=(int)label-1;
                return new RegimePrediction(signal, confidence, "ONNX_" + switch(signal) {
                    case 1 -> "BULLISH_UPTREND"; case -1 -> "BEARISH_DOWNTREND"; default -> "SIDEWAY_ACCUMULATION";
                });
            }
        } catch (Exception ex) {
            log.warn("ONNX unavailable; preserving SAA: {}", ex.getMessage());
            return unavailable("INFERENCE_ERROR");
        }
    }

    private RegimePrediction unavailable(String reason) {
        return new RegimePrediction(0, 0, "UNAVAILABLE_" + reason);
    }

    public Map<String,Object> modelStatus() {
        return Map.of("taaEnabled", taaEnabled, "featureVersion", CloseFeatures.VERSION, "featureCount", 12,
            "stock", status(stockSession), "gold", status(goldSession),
            "policy", "No heuristic signals; invalid or low-confidence inference preserves SAA");
    }

    private Map<String,Object> status(OrtSession session) {
        if(session == null) return Map.of("loaded",false);
        try { return Map.of("loaded",true,"metadata",session.getMetadata().getCustomMetadata()); }
        catch(Exception ex) { return Map.of("loaded",false,"reason","METADATA_ERROR"); }
    }

    private boolean matchesTicker(OrtSession session, String ticker) {
        try { return session != null && ticker.equals(session.getMetadata().getCustomMetadata().get("ticker")); }
        catch(Exception ex) { return false; }
    }

    /**
     * Dự báo trạng thái thị trường CỔ PHIẾU T+20 kèm confidence.
     * Chỉ dùng VNINDEX với schema close-v1; thiếu dữ liệu thì giữ SAA.
     */
    public RegimePrediction predictStockRegime() {
        if (!matchesTicker(stockSession, "VNINDEX")) return unavailable("STOCK_ASSET_MISMATCH");
        return predictWithConfidenceInternal(featureService.calculateFeatures("VNINDEX"), stockSession, stockModelLoaded);
    }

    /**
     * Dự báo trạng thái thị trường VÀNG T+20 kèm confidence.
     */
    public RegimePrediction predictGoldRegime() {
        // A global USD gold model is not a domestic SJC/VND model.
        if (!matchesTicker(goldSession, "GOLD_SJC")) return unavailable("GOLD_ASSET_MISMATCH");
        return predictWithConfidenceInternal(featureService.calculateFeatures("GOLD_SJC"), goldSession, goldModelLoaded);
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
