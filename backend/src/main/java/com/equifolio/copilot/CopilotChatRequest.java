package com.equifolio.copilot;

import jakarta.validation.constraints.NotBlank;

public class CopilotChatRequest {

    @NotBlank(message = "Nội dung câu hỏi không được để trống")
    private String message;

    private String apiKey;

    public CopilotChatRequest() {}

    public CopilotChatRequest(String message) {
        this.message = message;
    }

    public CopilotChatRequest(String message, String apiKey) {
        this.message = message;
        this.apiKey = apiKey;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getApiKey() {
        return apiKey;
    }

    public void setApiKey(String apiKey) {
        this.apiKey = apiKey;
    }
}
