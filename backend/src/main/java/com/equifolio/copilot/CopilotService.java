package com.equifolio.copilot;

import com.equifolio.ledger.CompoundSimulationDTO;
import com.equifolio.ledger.LedgerService;
import com.equifolio.ledger.PortfolioValuationDTO;
import com.equifolio.ledger.RiskMetricsDTO;
import com.equifolio.optimizer.OnnxRegimeService;
import com.equifolio.optimizer.PortfolioOptimizerService;
import com.equifolio.optimizer.RebalancePlanDTO;
import com.equifolio.profile.User;
import com.equifolio.profile.UserRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.auth.oauth2.AccessToken;
import com.google.auth.oauth2.GoogleCredentials;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.NumberFormat;
import java.time.Duration;
import java.util.*;

@Service
public class CopilotService {

    private static final Logger log = LoggerFactory.getLogger(CopilotService.class);

    private final LedgerService ledgerService;
    private final PortfolioOptimizerService optimizerService;
    private final OnnxRegimeService onnxRegimeService;
    private final UserRepository userRepository;
    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    @Value("${gemini.service-account-key-path:}")
    private String configuredSaKeyPath;

    @Value("${gemini.project-id:gen-lang-client-0656432358}")
    private String configuredProjectId;

    @Value("${gemini.location:us-central1}")
    private String configuredLocation;

    @Value("${gemini.model:gemini-2.5-flash-lite}")
    private String configuredModel;

    @Value("${gemini.api-key:}")
    private String configuredApiKey;

    private GoogleCredentials googleCredentials;
    private String resolvedProjectId;
    private boolean serviceAccountLoaded = false;
    private volatile String runtimeApiKey = null;

    public CopilotService(LedgerService ledgerService,
                          PortfolioOptimizerService optimizerService,
                          OnnxRegimeService onnxRegimeService,
                          UserRepository userRepository,
                          JdbcTemplate jdbcTemplate,
                          ObjectMapper objectMapper) {
        this.ledgerService = ledgerService;
        this.optimizerService = optimizerService;
        this.onnxRegimeService = onnxRegimeService;
        this.userRepository = userRepository;
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    @PostConstruct
    public void init() {
        resolvedProjectId = configuredProjectId;
        File keyFile = resolveServiceAccountKeyFile();

        if (keyFile != null && keyFile.exists() && keyFile.canRead()) {
            try {
                byte[] keyBytes = Files.readAllBytes(keyFile.toPath());
                JsonNode root = objectMapper.readTree(keyBytes);
                String pjId = root.path("project_id").asText();
                if (pjId != null && !pjId.isBlank()) {
                    resolvedProjectId = pjId;
                }

                googleCredentials = GoogleCredentials.fromStream(new ByteArrayInputStream(keyBytes))
                        .createScoped(List.of("https://www.googleapis.com/auth/cloud-platform"));
                googleCredentials.refreshIfExpired();
                serviceAccountLoaded = true;

                log.info("Loaded Google Cloud Service Account successfully from [{}] (Project: {}, Vertex AI Model: {}). Sẵn sàng phục vụ Copilot.",
                        keyFile.getName(), resolvedProjectId, configuredModel);
            } catch (Exception e) {
                log.warn("Failed to load Google Cloud Service Account key from [{}]: {}. Sẽ dùng fallback cấu hình.",
                        keyFile.getAbsolutePath(), e.getMessage());
            }
        } else {
            log.info("Không tìm thấy file Google Service Account key. Sẽ sử dụng API key hoặc Local RAG mode.");
        }
    }

    private File resolveServiceAccountKeyFile() {
        if (configuredSaKeyPath != null && !configuredSaKeyPath.isBlank()) {
            File f = new File(configuredSaKeyPath);
            if (f.exists()) return f;
        }

        String envCredentials = System.getenv("GOOGLE_APPLICATION_CREDENTIALS");
        if (envCredentials != null && !envCredentials.isBlank()) {
            File f = new File(envCredentials);
            if (f.exists()) return f;
        }

        // Tự động tìm kiếm file key chuẩn trong thư mục hiện tại hoặc thư mục cha
        List<String> candidatePaths = List.of(
                "gen-lang-client-0656432358-9a6fb12696b2.json",
                "../gen-lang-client-0656432358-9a6fb12696b2.json",
                "../../gen-lang-client-0656432358-9a6fb12696b2.json"
        );

        for (String p : candidatePaths) {
            File f = new File(p);
            if (f.exists() && f.isFile()) {
                return f;
            }
        }

        // Quét wildcard gen-lang-client-*.json ở thư mục cha và thư mục hiện tại
        File[] searchDirs = new File[]{ new File("."), new File(".."), new File("../..") };
        for (File dir : searchDirs) {
            if (dir.exists() && dir.isDirectory()) {
                File[] matches = dir.listFiles((d, name) -> name.startsWith("gen-lang-client-") && name.endsWith(".json"));
                if (matches != null && matches.length > 0) {
                    return matches[0];
                }
            }
        }

        return null;
    }

    public void setRuntimeApiKey(String key) {
        if (key != null && !key.trim().isEmpty()) {
            this.runtimeApiKey = key.trim();
        } else {
            this.runtimeApiKey = null;
        }
    }

    public String getEffectiveApiKey(String overrideKey) {
        if (overrideKey != null && !overrideKey.trim().isEmpty()) {
            return overrideKey.trim();
        }
        if (runtimeApiKey != null && !runtimeApiKey.trim().isEmpty()) {
            return runtimeApiKey.trim();
        }
        if (configuredApiKey != null && !configuredApiKey.trim().isEmpty()) {
            return configuredApiKey.trim();
        }
        String envKey = System.getenv("GEMINI_API_KEY");
        if (envKey != null && !envKey.trim().isEmpty()) {
            return envKey.trim();
        }
        return null;
    }

    public boolean hasApiKey() {
        return serviceAccountLoaded || getEffectiveApiKey(null) != null;
    }

    public boolean isServiceAccountLoaded() {
        return serviceAccountLoaded;
    }

    public String getModelName() {
        return configuredModel;
    }

    public String getProviderName() {
        return serviceAccountLoaded ? "Google Cloud Vertex AI (Service Account)" : "Google Gemini";
    }

    public String getAuthMode() {
        if (serviceAccountLoaded) return "SERVICE_ACCOUNT";
        if (getEffectiveApiKey(null) != null) return "API_KEY";
        return "LOCAL_RAG";
    }

    public CopilotChatResponse processMessage(Long userId, String userQuery) {
        return processMessage(userId, userQuery, null);
    }

    public CopilotChatResponse processMessage(Long userId, String userQuery, String clientApiKey) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy người dùng ID: " + userId));

        PortfolioValuationDTO valuation = ledgerService.calculatePortfolioValuation(userId);
        RebalancePlanDTO plan = optimizerService.generateRebalancePlan(userId);
        String marketRegime = onnxRegimeService.getLatestRegimeName();

        // 1. Tra cứu Hybrid RAG từ bảng vector_store bằng PostgreSQL Full-Text Search
        List<String> references = searchKnowledge(userQuery);

        // 2. Định dạng số tiền
        NumberFormat currencyFormat = NumberFormat.getInstance(new Locale("vi", "VN"));
        String navFormatted = currencyFormat.format(valuation.getTotalNetWorth()) + " ₫";
        String cashFormatted = currencyFormat.format(valuation.getCashBalance()) + " ₫";
        String stockFormatted = currencyFormat.format(valuation.getStockValue()) + " ₫";
        String goldFormatted = currencyFormat.format(valuation.getGoldValue()) + " ₫";
        String savingsFormatted = currencyFormat.format(valuation.getSavingsValue()) + " ₫";

        BigDecimal stockPct = valuation.getCurrentAllocations().getOrDefault("STOCK", BigDecimal.ZERO).multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN);
        BigDecimal goldPct = valuation.getCurrentAllocations().getOrDefault("GOLD", BigDecimal.ZERO).multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN);
        BigDecimal cashSavPct = valuation.getCurrentAllocations().getOrDefault("CASH_SAVINGS", BigDecimal.ZERO).multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN);

        // Chuẩn bị prompt hoàn chỉnh với ngữ cảnh tài chính
        String financialPrompt = buildFinancialPrompt(
                user, valuation, plan, marketRegime, references,
                navFormatted, cashFormatted, stockFormatted, goldFormatted, savingsFormatted,
                stockPct, goldPct, cashSavPct, userQuery, currencyFormat
        );

        // 3. Ưu tiên 1: Gọi Google Cloud Vertex AI qua Service Account Key
        if (serviceAccountLoaded && googleCredentials != null) {
            try {
                String aiReply = callGeminiVertexAi(financialPrompt, configuredModel);
                if (aiReply != null && !aiReply.isBlank()) {
                    return new CopilotChatResponse(aiReply, references);
                }
            } catch (Exception e) {
                log.warn("Vertex AI Gemini call failed (Will try API key or Native context engine): {}", e.getMessage());
            }
        }

        // 4. Ưu tiên 2: Gọi Google Gemini Generative Language API qua API Key (nếu có)
        String effectiveApiKey = getEffectiveApiKey(clientApiKey);
        if (effectiveApiKey != null && !effectiveApiKey.isEmpty()) {
            try {
                String geminiReply = callGeminiGenerativeLanguageApi(financialPrompt, effectiveApiKey, configuredModel);
                if (geminiReply != null && !geminiReply.isBlank()) {
                    return new CopilotChatResponse(geminiReply, references);
                }
            } catch (Exception e) {
                log.warn("Gemini API call failed (Falling back to native context engine): {}", e.getMessage());
            }
        }

        // 5. Fallback: Động cơ ngữ cảnh nội bộ (Native Context RAG Engine)
        StringBuilder reply = new StringBuilder();
        reply.append("Chào bạn **").append(user.getUsername()).append("**,\n\n");

        String queryLower = userQuery.toLowerCase();

        if (queryLower.contains("tái cơ cấu") || queryLower.contains("lệch") || queryLower.contains("drift") || queryLower.contains("bán") || queryLower.contains("mua")) {
            reply.append("Dựa trên phân tích Sổ cái kép thời gian thực, danh mục của bạn hiện tại:\n\n");
            reply.append("- **Tổng tài sản ròng (NAV):** ").append(navFormatted).append("\n");
            reply.append("- **Cơ cấu hiện thời:** Cổ phiếu **").append(stockPct).append("%** | Vàng **").append(goldPct).append("%** | Tiền mặt & Tiết kiệm **").append(cashSavPct).append("%**.\n");
            reply.append("- **Tình trạng độ lệch (Drift):** ").append(plan.isDriftDetected() ? "⚠️ Đang vượt ngưỡng an toàn (Lệch tối đa **" + plan.getMaxDriftPercent() + "%** > 5.0%)" : "✅ Đang ở trạng thái cân bằng tốt (Độ lệch **" + plan.getMaxDriftPercent() + "%** < 5.0%)").append(".\n\n");

            if (plan.isDriftDetected()) {
                reply.append("### 🎯 Lý do Đề xuất Tái cơ cấu:\n");
                reply.append("1. **Kỷ luật bảo vệ vốn (Markowitz SAA):** Tỷ trọng Cổ phiếu đang có xu hướng tăng nóng làm gia tăng rủi ro biến động ngoài mong đợi so với hồ sơ khẩu vị rủi ro (**").append(user.getRiskProfile()).append("**).\n");
                reply.append("2. **Bắt buộc lô chẵn sàn HOSE:** Mọi lệnh điều chỉnh đều được hệ thống làm tròn chẵn 100 cổ phiếu (ví dụ HPG, TCB) và làm tròn chỉ vàng nguyên để đảm bảo có thể khớp lệnh thực tế 100% trên bảng điện tử.\n");
                reply.append("3. **Khuyến nghị hành động:** Bạn có thể bấm nút **\"Xác nhận thực hiện tái cơ cấu\"** ngay trên màn hình Tổng quan để hệ thống tự động sinh bút toán kép chuẩn hóa lại tỷ trọng.\n\n");
            } else {
                reply.append("Danh mục của bạn đang vận hành ổn định trong biên độ cho phép. Bạn không cần vội vàng đảo danh mục lúc này, hãy kiên định với kỷ luật tích sản.\n\n");
            }
        } else if (queryLower.contains("vàng") || queryLower.contains("gold") || queryLower.contains("sjc")) {
            reply.append("Về tài sản **Vàng miếng SJC** trong danh mục của bạn:\n\n");
            reply.append("- Giá trị Vàng hiện nắm giữ: **").append(goldFormatted).append("** (chiếm **").append(goldPct).append("%** NAV).\n");
            reply.append("- **Vai trò chiến lược:** Vàng đóng vai trò là tài sản phòng thủ chống trượt giá và suy giảm kinh tế. Mô hình định lượng của EquiFolio khuyến nghị duy trì tỷ trọng Vàng quanh mốc 25% - 35% để giảm tối đa tỷ lệ sụt giảm sâu (Max Drawdown).\n\n");
        } else if (queryLower.contains("tiết kiệm") || queryLower.contains("lãi") || queryLower.contains("ngân hàng") || queryLower.contains("tích lũy") || queryLower.contains("tích sản")) {
            reply.append("Về kênh **Tiền gửi Tiết kiệm & Động cơ Lãi kép**:\n\n");
            reply.append("- Tổng số dư tiết kiệm hiện tại: **").append(savingsFormatted).append("** (kèm tiền mặt khả dụng: ").append(cashFormatted).append(").\n");
            reply.append("- **Động cơ Lãi kép:** Sổ tiết kiệm của bạn được tự động kích hoạt tính năng **Auto-Rollover**. Khi đến ngày đáo hạn, toàn bộ tiền lãi tích lũy sẽ được nhập vào gốc để tiếp tục sinh lời trong kỳ tiếp theo.\n");
            CompoundSimulationDTO sim = ledgerService.simulateCompoundGrowth(new BigDecimal("50000000"), new BigDecimal("5000000"), new BigDecimal("6.5"), 10);
            if (sim != null) {
                reply.append("- **Mô phỏng tích sản lãi kép (Kỳ hạn 10 năm):** Nếu duy trì góp thêm **").append(currencyFormat.format(sim.getMonthlyContribution())).append(" ₫/tháng** với lãi suất **").append(sim.getAnnualRate()).append("%/năm**:\n");
                reply.append("  + Tổng vốn tích lũy: **").append(currencyFormat.format(sim.getTotalContributed())).append(" ₫**\n");
                reply.append("  + Tiền lãi kép sinh lời: **+").append(currencyFormat.format(sim.getTotalInterestEarned())).append(" ₫**\n");
                reply.append("  + Giá trị tương lai (FV): **").append(currencyFormat.format(sim.getFutureValue())).append(" ₫** (Tài sản tăng **").append(sim.getWealthMultiplier()).append("x**).\n");
            }
            reply.append("- Bạn có thể vào tab **\"Tiết Kiệm\"** để dùng công cụ mô phỏng tương tác hoặc mở thêm sổ mới trích từ ví VND.\n\n");
        } else if (queryLower.contains("thị trường") || queryLower.contains("vnindex") || queryLower.contains("regime") || queryLower.contains("xu hướng")) {
            reply.append("### 📈 Dự báo Chu kỳ Thị trường (Embedded ONNX Model):\n\n");
            reply.append("- **Trạng thái nhận diện hiện tại:** `").append(marketRegime).append("`\n");
            reply.append("- **Cơ sở phân tích kỹ thuật:** Mô hình học máy dựa trên tổ hợp 15 chỉ báo xung lượng và dao động liên thị trường (RSI, MFI, MACD Histogram, Bollinger Bands, Tỷ lệ Gold/VN-Index). Nhờ vậy, hệ thống kịp thời phát hiện các vùng đảo chiều chu kỳ từ 20 phiên trước khi rủi ro lan rộng.\n\n");
        } else {
            reply.append("Cảm ơn bạn đã trao đổi với EquiFolio Copilot!\n\n");
            reply.append("Dựa trên tổng tài sản ròng **").append(navFormatted).append("** và trạng thái thị trường `").append(marketRegime).append("`, hệ thống khuyến nghị bạn:\n\n");
            reply.append("1. Duy trì tỷ trọng phân bổ kỷ luật giữa 3 chân kiềng: Cổ phiếu tăng trưởng, Vàng vật chất phòng thủ, và Tiết kiệm ngân hàng.\n");
            reply.append("2. Thường xuyên kiểm tra độ lệch danh mục (Drift) tại màn hình Tổng quan để kịp thời tái cân bằng khi thị trường biến động mạnh.\n\n");
        }

        // Bổ sung trích dẫn tri thức nếu tìm thấy
        if (!references.isEmpty()) {
            reply.append("📚 **Căn cứ tri thức tài chính liên quan:**\n");
            for (String ref : references) {
                reply.append("> *\"").append(ref.trim()).append("\"*\n");
            }
            reply.append("\n");
        }

        reply.append("*Lưu ý nguyên tắc Zero-Trust: EquiFolio Copilot chỉ cung cấp các phân tích toán học và gợi ý định lượng khách quan. Nhà đầu tư chủ động xem xét và chịu trách nhiệm đối với quyết định đặt lệnh ngoài đời thực.*");

        return new CopilotChatResponse(reply.toString(), references);
    }

    private String buildFinancialPrompt(User user,
                                        PortfolioValuationDTO valuation,
                                        RebalancePlanDTO plan,
                                        String marketRegime,
                                        List<String> references,
                                        String navFormatted,
                                        String cashFormatted,
                                        String stockFormatted,
                                        String goldFormatted,
                                        String savingsFormatted,
                                        BigDecimal stockPct,
                                        BigDecimal goldPct,
                                        BigDecimal cashSavPct,
                                        String userQuery,
                                        NumberFormat currencyFormat) {

        StringBuilder promptBuilder = new StringBuilder();
        promptBuilder.append("Bạn là EquiFolio Copilot, trợ lý tư vấn tài chính định lượng và quản lý tài sản cá nhân thông minh (Robo-Advisor) của nền tảng EquiFolio.\n");
        promptBuilder.append("Dưới đây là dữ liệu tài chính thời gian thực của người dùng được trích xuất từ Hệ thống Sổ cái kép ngân hàng (Double-Entry Ledger) và Mô hình Học máy ONNX:\n\n");

        promptBuilder.append("[HỒ SƠ KHÁCH HÀNG]\n");
        promptBuilder.append("- Họ và tên: ").append(user.getUsername()).append("\n");
        promptBuilder.append("- Khẩu vị rủi ro: ").append(user.getRiskProfile()).append(" (Điểm rủi ro: ").append(user.getRiskScore()).append("/100, Hệ số λ: ").append(user.getRiskAversionLambda()).append(")\n\n");

        promptBuilder.append("[TỔNG TÀI SẢN RÒNG & CƠ CẤU DANH MỤC HIỆN THỜI]\n");
        promptBuilder.append("- Tổng tài sản ròng (NAV): ").append(navFormatted).append("\n");
        promptBuilder.append("- Tiền mặt khả dụng: ").append(cashFormatted).append("\n");
        promptBuilder.append("- Cổ phiếu: ").append(stockFormatted).append(" (chiếm ").append(stockPct).append("% NAV)\n");
        promptBuilder.append("- Vàng miếng SJC: ").append(goldFormatted).append(" (chiếm ").append(goldPct).append("% NAV)\n");
        promptBuilder.append("- Tiền gửi Tiết kiệm: ").append(savingsFormatted).append(" (chiếm ").append(cashSavPct).append("% NAV)\n\n");

        promptBuilder.append("[HIỆU SUẤT LÃI/LỖ & GIÁ VỐN DANH MỤC (PORTFOLIO P&L)]\n");
        promptBuilder.append("- Tổng giá vốn: ").append(currencyFormat.format(valuation.getTotalCostBasis())).append(" ₫\n");
        promptBuilder.append("- Lãi/Lỗ chưa chốt (Unrealized P&L): ").append(currencyFormat.format(valuation.getTotalUnrealizedPnL())).append(" ₫ (").append(valuation.getTotalPnLPercent()).append("%)\n");
        promptBuilder.append("- Lãi/Lỗ đã chốt lũy kế (Realized P&L): ").append(currencyFormat.format(valuation.getTotalRealizedPnL())).append(" ₫\n");
        promptBuilder.append("- Chi tiết từng mã nắm giữ:\n");
        for (PortfolioValuationDTO.HoldingItem h : valuation.getHoldings()) {
            if ("STOCK".equalsIgnoreCase(h.getAssetClass()) || "GOLD".equalsIgnoreCase(h.getAssetClass())) {
                promptBuilder.append("  + Mã ").append(h.getTicker()).append(": ")
                        .append(h.getQuantity()).append(" đơn vị | ")
                        .append("Giá vốn: ").append(currencyFormat.format(h.getCostPrice())).append(" ₫ | ")
                        .append("Thị giá: ").append(currencyFormat.format(h.getCurrentPrice())).append(" ₫ | ")
                        .append("P&L: ").append(h.getUnrealizedPnLPercent()).append("% (").append(currencyFormat.format(h.getUnrealizedPnL())).append(" ₫)\n");
            }
        }
        promptBuilder.append("\n");

        RiskMetricsDTO risk = ledgerService.calculateRiskMetrics(user.getId());
        if (risk != null) {
            promptBuilder.append("[CHỈ SỐ RỦI RO & ĐO LƯỜNG HIỆU SUẤT CHUẨN MỰC]\n");
            promptBuilder.append("- Sharpe Ratio: ").append(risk.getSharpeRatio()).append("\n");
            promptBuilder.append("- Max Drawdown (Sụt giảm tối đa): ").append(risk.getMaxDrawdownPercent()).append("%\n");
            promptBuilder.append("- Độ biến động năm (Annual Volatility): ").append(risk.getAnnualizedVolatilityPercent()).append("%\n");
            promptBuilder.append("- Alpha vượt trội vs VN-Index: ").append(risk.getAlphaPercent()).append("%\n");
            promptBuilder.append("- Đánh giá rủi ro: ").append(risk.getInterpretation()).append("\n\n");
        }

        promptBuilder.append("[MỤC TIÊU PHÂN BỔ SAA & TÁI CƠ CẤU]\n");
        promptBuilder.append("- Mục tiêu SAA chuẩn: Cổ phiếu 35%, Vàng 35%, Tiết kiệm & Tiền mặt 30%\n");
        promptBuilder.append("- Trạng thái lệch tỷ trọng (Drift): ").append(plan.isDriftDetected() ? "Lệch " + plan.getMaxDriftPercent() + "% (VƯỢT ngưỡng an toàn 5%)" : "Cân bằng tối ưu (Độ lệch " + plan.getMaxDriftPercent() + "% < 5%)").append("\n");
        promptBuilder.append("- Tóm tắt đề xuất: ").append(plan.getExecutiveSummary()).append("\n");
        promptBuilder.append("- Bắt buộc lô chẵn sàn HOSE: Khối lượng giao dịch cổ phiếu phải là bội số của 100 cp; Vàng SJC tính theo bước chỉ nguyên.\n\n");

        promptBuilder.append("[DỰ BÁO CHU KỲ THỊ TRƯỜNG TỪ MÔ HÌNH HỌC MÁY ONNX]\n");
        promptBuilder.append("- Trạng thái chu kỳ nhận diện: ").append(marketRegime).append("\n\n");

        CompoundSimulationDTO sim = ledgerService.simulateCompoundGrowth(new BigDecimal("50000000"), new BigDecimal("5000000"), new BigDecimal("6.5"), 10);
        if (sim != null) {
            promptBuilder.append("[KẾT QUẢ MÔ PHỎNG LÃI KÉP TỪ ENGINE TÍNH TOÁN (ANTI-HALLUCINATION)]\n");
            promptBuilder.append("- Tham số kịch bản: Vốn ban đầu 50.000.000 ₫, tích lũy 5.000.000 ₫/tháng, lãi suất 6.5%/năm trong 10 năm.\n");
            promptBuilder.append("- Tổng vốn tích lũy: ").append(currencyFormat.format(sim.getTotalContributed())).append(" ₫\n");
            promptBuilder.append("- Tổng tiền lãi sinh lời: ").append(currencyFormat.format(sim.getTotalInterestEarned())).append(" ₫\n");
            promptBuilder.append("- Giá trị tương lai (FV): ").append(currencyFormat.format(sim.getFutureValue())).append(" ₫ (Bội số: ").append(sim.getWealthMultiplier()).append("x)\n\n");
        }

        if (references != null && !references.isEmpty()) {
            promptBuilder.append("[TRI THỨC THAM CHIẾU TỪ POSTGRESQL RAG]\n");
            for (String ref : references) {
                promptBuilder.append("- ").append(ref.trim()).append("\n");
            }
            promptBuilder.append("\n");
        }

        promptBuilder.append("[YÊU CẦU TRẢ LỜI]\n");
        promptBuilder.append("1. Trả lời trực tiếp vào câu hỏi của khách hàng bằng tiếng Việt chuẩn mực, lịch thiệp, giọng điệu chuyên gia quản lý gia sản tư nhân (Private Wealth Advisor).\n");
        promptBuilder.append("2. Lồng ghép các số liệu thực tế bên trên (NAV, tỷ trọng, cổ phiếu nắm giữ, số chỉ vàng) để phân tích có bằng chứng định lượng thuyết phục.\n");
        promptBuilder.append("3. Định dạng Markdown rõ ràng, gãy gọn, có chia đề mục hoặc gạch đầu dòng.\n");
        promptBuilder.append("4. Cuối câu trả lời, luôn có lưu ý nguyên tắc Zero-Trust: Khuyến nghị mang tính chất cố vấn phân tích định lượng, khách hàng tự kiểm tra trước khi đặt lệnh ngoài app chứng khoán thực tế.\n\n");

        promptBuilder.append("Câu hỏi của khách hàng:\n\"");
        promptBuilder.append(userQuery);
        promptBuilder.append("\"\n");

        return promptBuilder.toString();
    }

    /**
     * Gọi Google Cloud Vertex AI qua Google Credentials (Service Account Key)
     */
    private String callGeminiVertexAi(String prompt, String model) throws Exception {
        googleCredentials.refreshIfExpired();
        AccessToken token = googleCredentials.getAccessToken();
        String accessToken = token.getTokenValue();

        String activeModel = model;
        String endpoint = String.format("https://%s-aiplatform.googleapis.com/v1/projects/%s/locations/%s/publishers/google/models/%s:generateContent",
                configuredLocation, resolvedProjectId, configuredLocation, activeModel);

        Map<String, Object> textPart = Map.of("text", prompt);
        Map<String, Object> content = Map.of(
                "role", "user",
                "parts", List.of(textPart)
        );
        Map<String, Object> generationConfig = Map.of(
                "temperature", 0.4,
                "maxOutputTokens", 2048
        );
        Map<String, Object> requestBody = Map.of(
                "contents", List.of(content),
                "generationConfig", generationConfig
        );

        String jsonPayload = objectMapper.writeValueAsString(requestBody);

        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(endpoint))
                .timeout(Duration.ofSeconds(45))
                .header("Content-Type", "application/json")
                .header("Authorization", "Bearer " + accessToken)
                .POST(HttpRequest.BodyPublishers.ofString(jsonPayload, StandardCharsets.UTF_8))
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));

        // Tự động fallback sang gemini-2.5-flash-lite nếu model chỉ định bị 404
        if (response.statusCode() == 404 && !activeModel.equals("gemini-2.5-flash-lite")) {
            log.warn("Vertex AI Model [{}] trả về 404, tự động chuyển sang [gemini-2.5-flash-lite]...", activeModel);
            String fallbackEndpoint = String.format("https://%s-aiplatform.googleapis.com/v1/projects/%s/locations/%s/publishers/google/models/gemini-2.5-flash-lite:generateContent",
                    configuredLocation, resolvedProjectId, configuredLocation);
            HttpRequest retryReq = HttpRequest.newBuilder()
                    .uri(URI.create(fallbackEndpoint))
                    .timeout(Duration.ofSeconds(45))
                    .header("Content-Type", "application/json")
                    .header("Authorization", "Bearer " + accessToken)
                    .POST(HttpRequest.BodyPublishers.ofString(jsonPayload, StandardCharsets.UTF_8))
                    .build();
            response = client.send(retryReq, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        }

        if (response.statusCode() == 200) {
            JsonNode root = objectMapper.readTree(response.body());
            JsonNode candidates = root.path("candidates");
            if (candidates.isArray() && !candidates.isEmpty()) {
                JsonNode parts = candidates.get(0).path("content").path("parts");
                if (parts.isArray() && !parts.isEmpty()) {
                    return parts.get(0).path("text").asText();
                }
            }
        }

        throw new IllegalStateException("Google Cloud Vertex AI error (HTTP " + response.statusCode() + "): " + response.body());
    }

    /**
     * Fallback gọi Google Generative Language API nếu dùng direct API Key
     */
    private String callGeminiGenerativeLanguageApi(String prompt, String apiKey, String model) throws Exception {
        String endpoint = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + apiKey.trim();

        Map<String, Object> textPart = Map.of("text", prompt);
        Map<String, Object> content = Map.of("parts", List.of(textPart));
        Map<String, Object> generationConfig = Map.of(
                "temperature", 0.4,
                "maxOutputTokens", 2048
        );
        Map<String, Object> requestBody = Map.of(
                "contents", List.of(content),
                "generationConfig", generationConfig
        );

        String jsonPayload = objectMapper.writeValueAsString(requestBody);

        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(endpoint))
                .timeout(Duration.ofSeconds(30))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(jsonPayload, StandardCharsets.UTF_8))
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));

        if (response.statusCode() == 200) {
            JsonNode root = objectMapper.readTree(response.body());
            JsonNode candidates = root.path("candidates");
            if (candidates.isArray() && !candidates.isEmpty()) {
                JsonNode parts = candidates.get(0).path("content").path("parts");
                if (parts.isArray() && !parts.isEmpty()) {
                    return parts.get(0).path("text").asText();
                }
            }
        }
        throw new IllegalStateException("Google Gemini API error (HTTP " + response.statusCode() + "): " + response.body());
    }

    private List<String> searchKnowledge(String query) {
        List<String> list = new ArrayList<>();
        try {
            String cleanQuery = query.replaceAll("[^a-zA-Z0-9\\s]", " ").trim();
            if (!cleanQuery.isEmpty()) {
                String sql = "SELECT content FROM vector_store WHERE tsv @@ plainto_tsquery('simple', ?) LIMIT 2";
                List<String> docs = jdbcTemplate.query(sql, (rs, rowNum) -> rs.getString("content"), cleanQuery);
                if (docs != null && !docs.isEmpty()) {
                    list.addAll(docs);
                }
            }
        } catch (Exception e) {
            // Không ngắt luồng nếu DB chưa cấu hình extension vector
        }
        return list;
    }
}
