package com.equifolio.common;

import com.equifolio.profile.User;
import java.util.Set;

/** Explicitly seeded testing accounts; ordinary user history stays observed-only. */
public final class DemoData {
    private static final Set<String> ACCOUNTS = Set.of("demo_balanced", "demo_growth", "demo_defensive",
        "demo_balanced_extended", "demo_growth_extended", "demo_defensive_extended", "demo_etf_growth_3y");
    private DemoData() {}

    public static boolean isDemoAccount(User user) {
        return user != null && ACCOUNTS.contains(user.getUsername())
            && (user.getUsername() + "@demo.equifolio.test").equals(user.getEmail());
    }

    public static boolean isAnalysisSource(String source) {
        return "OBSERVED".equals(source) || "DEMO".equals(source);
    }
}
