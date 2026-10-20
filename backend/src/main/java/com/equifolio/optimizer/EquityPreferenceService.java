package com.equifolio.optimizer;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Set;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@Service
public class EquityPreferenceService {
    public record Preference(String mode, BigDecimal etfWeight) {}
    private final JdbcTemplate jdbc;
    public EquityPreferenceService(JdbcTemplate jdbc) { this.jdbc=jdbc; }
    public Preference get(Long userId) {
        var rows=jdbc.query("SELECT mode,etf_weight FROM equity_investment_preferences WHERE user_id=?",
            (rs,n)->new Preference(rs.getString(1),rs.getBigDecimal(2)),userId);
        return rows.isEmpty()?null:rows.get(0);
    }
    public Preference save(Long userId, Preference preference) {
        if(preference==null || preference.mode()==null || !Set.of("ETF","STOCKS","MIXED").contains(preference.mode())
            || preference.etfWeight()==null || preference.etfWeight().scale()>4)
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Chọn cách đầu tư và tỷ lệ ETF hợp lệ");
        BigDecimal weight=preference.etfWeight();
        boolean valid=switch(preference.mode()) {
            case "ETF" -> weight.compareTo(BigDecimal.ONE)==0;
            case "STOCKS" -> weight.signum()==0;
            default -> weight.signum()>0 && weight.compareTo(BigDecimal.ONE)<0;
        };
        if(!valid)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Tỷ lệ ETF không phù hợp với cách đầu tư");
        var normalized=new Preference(preference.mode(),weight.setScale(4,RoundingMode.UNNECESSARY));
        jdbc.update("INSERT INTO equity_investment_preferences(user_id,mode,etf_weight) VALUES(?,?,?) "
            +"ON CONFLICT(user_id) DO UPDATE SET mode=EXCLUDED.mode,etf_weight=EXCLUDED.etf_weight,updated_at=CURRENT_TIMESTAMP",
            userId,normalized.mode(),normalized.etfWeight());
        return normalized;
    }
}
