package com.equifolio.profile;

import jakarta.validation.constraints.NotEmpty;
import java.util.List;

public class RiskSurveyRequest {

    @NotEmpty(message = "Danh sách câu trả lời không được để trống")
    private List<AnswerItem> answers;

    public static class AnswerItem {
        private int questionId;
        private String selectedOption; // 'A', 'B', 'C', 'D'
        private int score;             // 0, 7, 14, 20

        public AnswerItem() {}

        public int getQuestionId() { return questionId; }
        public void setQuestionId(int questionId) { this.questionId = questionId; }

        public String getSelectedOption() { return selectedOption; }
        public void setSelectedOption(String selectedOption) { this.selectedOption = selectedOption; }

        public int getScore() { return score; }
        public void setScore(int score) { this.score = score; }
    }

    public RiskSurveyRequest() {}

    public List<AnswerItem> getAnswers() { return answers; }
    public void setAnswers(List<AnswerItem> answers) { this.answers = answers; }
}
