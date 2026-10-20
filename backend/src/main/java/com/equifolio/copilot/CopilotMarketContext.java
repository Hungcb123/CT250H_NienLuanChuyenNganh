package com.equifolio.copilot;

import com.equifolio.optimizer.RebalancePlanDTO;
import java.util.Locale;

/** Use the same selected forecast as the Market tab, including its horizon and score semantics. */
final class CopilotMarketContext {
    private CopilotMarketContext() {}

    static String from(RebalancePlanDTO plan) {
        int horizon = plan.getHorizonSessions();
        var predictions = plan.getMlPredictions();
        var stock = predictions == null ? null : predictions.stream()
                .filter(p -> "STOCK".equals(p.getAssetClass())).findFirst().orElse(null);
        String prefix = "VNINDEX · T+" + horizon + " phiên\n";
        if (stock == null) return prefix + "Trạng thái: UNAVAILABLE — chưa có dự báo; không suy diễn hướng tăng/giảm hoặc độ tin cậy.";
        var nativeForecast = stock.getNativeForecast();
        boolean unavailable = stock.getRegimeName() == null || stock.getRegimeName().startsWith("UNAVAILABLE")
                || (nativeForecast != null && !nativeForecast.available());
        String identity = "Mô hình: " + stock.getModelName() + "\n";
        if (unavailable) return prefix + identity + "Trạng thái: UNAVAILABLE — chưa có dự báo hợp lệ; không suy diễn hướng tăng/giảm hoặc độ tin cậy.";
        String direction = switch (stock.getSignal()) {
            case -1 -> "Nghiêng giảm";
            case 1 -> "Nghiêng tăng";
            default -> "Đi ngang";
        };
        String result = prefix + identity + "Hướng dự báo: " + direction + "\nNhãn: " + stock.getRegimeName();
        if (nativeForecast != null) {
            result += "\nPhiên dữ liệu: " + nativeForecast.session()
                    + "\nĐiểm quyết định [giảm, đi ngang, tăng]: " + nativeForecast.classScores()
                    + "\nĐiểm thuần: " + nativeForecast.netScore()
                    + "\nCác điểm trên chưa hiệu chỉnh thành xác suất; KHÔNG gọi là độ tin cậy hoặc xác suất dự báo.";
        } else {
            result += String.format(Locale.ROOT, "\nĐiểm mô hình: %.4f; chưa xác nhận hiệu chỉnh thành xác suất, không gọi là xác suất thị trường tăng/giảm.", stock.getConfidence());
        }
        return result;
    }
}
