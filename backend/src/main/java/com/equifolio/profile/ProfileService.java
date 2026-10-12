package com.equifolio.profile;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class ProfileService {

    private final UserRepository userRepository;
    private final PortfolioTargetRepository portfolioTargetRepository;

    public ProfileService(UserRepository userRepository, PortfolioTargetRepository portfolioTargetRepository) {
        this.userRepository = userRepository;
        this.portfolioTargetRepository = portfolioTargetRepository;
    }

    public User getOrCreateDemoUser() {
        return userRepository.findById(1L).orElseGet(() -> {
            User demo = new User();
            demo.setId(1L);
            demo.setUsername("alex_nguyen");
            demo.setEmail("alex.nguyen@equifolio.vn");
            demo.setPasswordHash("$2a$10$nWNg7Kr302JjEnwZWY8r.OlRwH5gNj5NCYIWWY6tXmMRwqdOWFoRe");
            demo.setRiskScore(63);
            demo.setRiskAversionLambda(new BigDecimal("4.33"));
            demo.setRiskProfile("BALANCED");
            return userRepository.save(demo);
        });
    }

    public User getUserById(Long userId) {
        return userRepository.findById(userId).orElseGet(this::getOrCreateDemoUser);
    }

    @Transactional
    public RiskSurveyResponse processRiskSurvey(Long userId, RiskSurveyRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy người dùng ID: " + userId));

        // 1. Tính tổng điểm Risk Score (0 - 100)
        int totalScore = request.getAnswers().stream()
                .mapToInt(RiskSurveyRequest.AnswerItem::getScore)
                .sum();
        totalScore = Math.max(0, Math.min(100, totalScore));

        // 2. Ánh xạ sang Hệ số Ngại Rủi ro λ = 10.0 - 0.09 * Risk Score
        double lambdaVal = 10.0 - (0.09 * totalScore);
        BigDecimal lambda = BigDecimal.valueOf(lambdaVal).setScale(2, RoundingMode.HALF_EVEN);

        // 3. Phân loại nhóm hồ sơ và xác lập Tỷ trọng Chiến lược SAA
        String profile;
        Map<String, BigDecimal> allocation = new HashMap<>();
        String summary;

        if (totalScore < 40) {
            profile = "CONSERVATIVE";
            allocation.put("STOCK", new BigDecimal("0.1500"));
            allocation.put("GOLD", new BigDecimal("0.2500"));
            allocation.put("SAVINGS", new BigDecimal("0.4500"));
            allocation.put("CASH", new BigDecimal("0.1500"));
            allocation.put("CASH_SAVINGS", new BigDecimal("0.6000"));
            summary = "Hồ sơ của bạn thuộc nhóm Bảo thủ. Ưu tiên số một là bảo toàn vốn gốc, hạn chế biến động và tạo dòng tiền tích sản ổn định qua Tiền gửi tiết kiệm và Vàng.";
        } else if (totalScore < 70) {
            profile = "BALANCED";
            allocation.put("STOCK", new BigDecimal("0.3500"));
            allocation.put("GOLD", new BigDecimal("0.3500"));
            allocation.put("SAVINGS", new BigDecimal("0.2000"));
            allocation.put("CASH", new BigDecimal("0.1000"));
            allocation.put("CASH_SAVINGS", new BigDecimal("0.3000"));
            summary = "Hồ sơ của bạn thuộc nhóm Cân bằng. Bạn có năng lực tài chính ổn định và chấp nhận mức độ biến động vừa phải để tối ưu hóa tăng trưởng tài sản trung và dài hạn.";
        } else {
            profile = "GROWTH";
            allocation.put("STOCK", new BigDecimal("0.6000"));
            allocation.put("GOLD", new BigDecimal("0.2000"));
            allocation.put("SAVINGS", new BigDecimal("0.1500"));
            allocation.put("CASH", new BigDecimal("0.0500"));
            allocation.put("CASH_SAVINGS", new BigDecimal("0.2000"));
            summary = "Hồ sơ của bạn thuộc nhóm Tăng trưởng. Bạn có khẩu vị rủi ro cao, sẵn sàng đón nhận biến động để tối đa hóa tỷ suất sinh lời từ thị trường Cổ phiếu.";
        }

        // 4. Lưu cập nhật vào DB
        user.setRiskScore(totalScore);
        user.setRiskAversionLambda(lambda);
        user.setRiskProfile(profile);
        userRepository.save(user);

        // Cập nhật bảng portfolio_targets
        for (Map.Entry<String, BigDecimal> entry : allocation.entrySet()) {
            PortfolioTarget target = portfolioTargetRepository
                    .findByUserIdAndAssetClass(userId, entry.getKey())
                    .orElse(new PortfolioTarget(user, entry.getKey(), entry.getValue()));
            target.setTargetWeight(entry.getValue());
            target.setUpdatedAt(Instant.now());
            portfolioTargetRepository.save(target);
        }

        return new RiskSurveyResponse(totalScore, profile, lambda, allocation, summary);
    }

    @Transactional
    public Map<String, BigDecimal> updateCustomTargets(Long userId, UpdateTargetsRequest req) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy người dùng ID: " + userId));

        BigDecimal total = req.getStock().add(req.getGold()).add(req.getSavings()).add(req.getCash());
        if (total.subtract(BigDecimal.ONE).abs().compareTo(new BigDecimal("0.01")) > 0) {
            throw new IllegalArgumentException("Tổng tỷ trọng 4 lớp tài sản phải bằng 100% (Hiện tại: " +
                    total.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_EVEN) + "%)");
        }

        Map<String, BigDecimal> allocation = new HashMap<>();
        allocation.put("STOCK", req.getStock());
        allocation.put("GOLD", req.getGold());
        allocation.put("SAVINGS", req.getSavings());
        allocation.put("CASH", req.getCash());
        allocation.put("CASH_SAVINGS", req.getCash().add(req.getSavings()));

        for (Map.Entry<String, BigDecimal> entry : allocation.entrySet()) {
            PortfolioTarget target = portfolioTargetRepository
                    .findByUserIdAndAssetClass(userId, entry.getKey())
                    .orElse(new PortfolioTarget(user, entry.getKey(), entry.getValue()));
            target.setTargetWeight(entry.getValue());
            target.setUpdatedAt(Instant.now());
            portfolioTargetRepository.save(target);
        }

        return allocation;
    }

    @Transactional(readOnly = true)
    public Map<String, BigDecimal> getTargetsByUserId(Long userId) {
        List<PortfolioTarget> targets = portfolioTargetRepository.findByUserId(userId);
        Map<String, BigDecimal> map = new HashMap<>();
        for (PortfolioTarget t : targets) {
            map.put(t.getAssetClass(), t.getTargetWeight());
        }
        return map;
    }
}
