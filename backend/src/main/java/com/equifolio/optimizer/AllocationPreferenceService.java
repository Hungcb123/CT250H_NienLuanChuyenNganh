package com.equifolio.optimizer;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

@Service
public class AllocationPreferenceService {
    public record Preference(String mode, int horizonSessions) {}
    private final JdbcTemplate jdbc;
    public AllocationPreferenceService(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    public Preference get(Long userId) {
        var rows = jdbc.query("SELECT mode,horizon_sessions FROM allocation_preferences WHERE user_id=?",
            (rs, n) -> new Preference(rs.getString(1), rs.getInt(2)), userId);
        return rows.isEmpty() ? new Preference("SAA", 20) : rows.get(0);
    }
    public Preference save(Long userId, Preference preference) {
        if (preference == null || !("SAA".equals(preference.mode()) || "TAA".equals(preference.mode()))
            || !java.util.Set.of(20,60,120).contains(preference.horizonSessions()))
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Chọn SAA/TAA và kỳ hạn 20, 60 hoặc 120 phiên");
        jdbc.update("INSERT INTO allocation_preferences(user_id,mode,horizon_sessions) VALUES (?,?,?) "
            + "ON CONFLICT(user_id) DO UPDATE SET mode=EXCLUDED.mode,horizon_sessions=EXCLUDED.horizon_sessions,updated_at=CURRENT_TIMESTAMP",
            userId, preference.mode(), preference.horizonSessions());
        return preference;
    }
}
