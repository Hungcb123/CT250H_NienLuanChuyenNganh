package com.equifolio.optimizer;

/**
 * Kết quả dự báo từ mô hình ONNX Regime Classification.
 * Chứa cả Signal (hướng) và P_confidence (độ tin cậy) cần thiết cho công thức TAA:
 * Δw = Signal × P_confidence × Δw_max
 */
public record RegimePrediction(
        int signal,            // -1 (Bearish), 0 (Sideway), +1 (Bullish)
        double confidence,     // Xác suất của nhãn thắng thế (0.0 → 1.0)
        String regimeName      // Tên nhãn đọc được: "BULLISH", "SIDEWAY", "BEARISH"
) {

    /**
     * Tạo prediction mặc định khi không có model hoặc lỗi inference.
     * Signal = 0 (Sideway) với confidence = 0.33 → Δw ≈ 0 → giữ nguyên SAA.
     */
    public static RegimePrediction neutral() {
        return new RegimePrediction(0, 0.33, "SIDEWAY_NEUTRAL");
    }

    /**
     * Tạo prediction từ signal int với confidence mặc định 0.60 (cho fallback heuristic).
     */
    public static RegimePrediction fromSignal(int signal) {
        String name = switch (signal) {
            case 1 -> "BULLISH_UPTREND";
            case -1 -> "BEARISH_DOWNTREND";
            default -> "SIDEWAY_ACCUMULATION";
        };
        return new RegimePrediction(signal, 0.60, name);
    }
}
