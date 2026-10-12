package com.equifolio.copilot;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

public class CopilotChatResponse {
    private String reply;
    private Instant timestamp;
    private List<String> referenceSources = new ArrayList<>();

    public CopilotChatResponse() {
        this.timestamp = Instant.now();
    }

    public CopilotChatResponse(String reply, List<String> referenceSources) {
        this.reply = reply;
        this.timestamp = Instant.now();
        this.referenceSources = referenceSources;
    }

    public String getReply() { return reply; }
    public void setReply(String reply) { this.reply = reply; }

    public Instant getTimestamp() { return timestamp; }
    public void setTimestamp(Instant timestamp) { this.timestamp = timestamp; }

    public List<String> getReferenceSources() { return referenceSources; }
    public void setReferenceSources(List<String> referenceSources) { this.referenceSources = referenceSources; }
}
