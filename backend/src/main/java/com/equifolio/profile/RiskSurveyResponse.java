package com.equifolio.profile;

import java.math.BigDecimal;
import java.util.Map;

public class RiskSurveyResponse {
    private int totalRiskScore;
    private String riskProfile; // 'CONSERVATIVE', 'BALANCED', 'GROWTH'
    private BigDecimal riskAversionLambda;
    private Map<String, BigDecimal> recommendedAllocation;
    private String profileSummary;

    public RiskSurveyResponse() {}

    public RiskSurveyResponse(int totalRiskScore, String riskProfile, BigDecimal riskAversionLambda,
                              Map<String, BigDecimal> recommendedAllocation, String profileSummary) {
        this.totalRiskScore = totalRiskScore;
        this.riskProfile = riskProfile;
        this.riskAversionLambda = riskAversionLambda;
        this.recommendedAllocation = recommendedAllocation;
        this.profileSummary = profileSummary;
    }

    public int getTotalRiskScore() { return totalRiskScore; }
    public void setTotalRiskScore(int totalRiskScore) { this.totalRiskScore = totalRiskScore; }

    public String getRiskProfile() { return riskProfile; }
    public void setRiskProfile(String riskProfile) { this.riskProfile = riskProfile; }

    public BigDecimal getRiskAversionLambda() { return riskAversionLambda; }
    public void setRiskAversionLambda(BigDecimal riskAversionLambda) { this.riskAversionLambda = riskAversionLambda; }

    public Map<String, BigDecimal> getRecommendedAllocation() { return recommendedAllocation; }
    public void setRecommendedAllocation(Map<String, BigDecimal> recommendedAllocation) { this.recommendedAllocation = recommendedAllocation; }

    public String getProfileSummary() { return profileSummary; }
    public void setProfileSummary(String profileSummary) { this.profileSummary = profileSummary; }
}
