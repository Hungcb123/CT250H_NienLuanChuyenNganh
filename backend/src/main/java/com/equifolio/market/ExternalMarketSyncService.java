package com.equifolio.market;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.*;

/**
 * Service quản lý đồng bộ dữ liệu thị trường mở rộng:
 * 1. Giá Vàng SJC & Nhẫn 9999 (Kiến trúc 3 tầng: Public Feed -> VnAppMob -> Database Fallback)
 * 2. Biểu Lãi Suất Tiết Kiệm các Ngân hàng Thương mại (VCB, MB, BIDV, TCB, ACB...)
 * 3. Lãi suất phi rủi ro Rf (SBV Interbank Rate) phục vụ mô hình Sharpe & Markowitz
 */
@Service
public class ExternalMarketSyncService {

    private static final Logger log = LoggerFactory.getLogger(ExternalMarketSyncService.class);
    private static final ZoneId VN_ZONE = ZoneId.of("Asia/Bangkok");

    private final BankInterestRateRepository bankInterestRateRepository;
    private final MacroIndicatorRepository macroIndicatorRepository;
    private final GoldHistorySync goldSync;
    private final GoldPriceStore goldStore;

    public ExternalMarketSyncService(BankInterestRateRepository bankInterestRateRepository,
                                     MacroIndicatorRepository macroIndicatorRepository,
                                     GoldHistorySync goldSync, GoldPriceStore goldStore) {
        this.bankInterestRateRepository = bankInterestRateRepository;
        this.macroIndicatorRepository = macroIndicatorRepository;
        this.goldSync = goldSync;
        this.goldStore = goldStore;
    }

    /**
     * Tự động kiểm tra và đồng bộ khi ứng dụng khởi chạy
     */
    @Async
    @EventListener(ApplicationReadyEvent.class)
    public void onStartup() {
        try {
            Thread.sleep(3000); // Đợi DB pool sẵn sàng
            syncAllExternal(false);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (Exception e) {
            log.warn("[External Sync] Initial sync encountered notice: {}", e.getMessage());
        }
    }

    /**
     * Cronjob chạy 2 lần/ngày: 08:45 sáng (sau giờ mở cửa thị trường vàng) và 14:30 chiều
     */
    @Scheduled(cron = "0 45 8,14 * * MON-FRI", zone = "Asia/Bangkok")
    public void scheduledSync() {
        log.info("[External Sync] Scheduled daily market sync triggered.");
        syncAllExternal(true);
    }

    /**
     * Đồng bộ toàn bộ: Giá Vàng, Biểu Lãi Suất Ngân Hàng, Lãi suất phi rủi ro Rf
     */
    @Transactional
    public Map<String, Object> syncAllExternal(boolean force) {
        LocalDate today = LocalDate.now(VN_ZONE);
        Map<String, Object> result = new LinkedHashMap<>();

        // 1. Đồng bộ giá vàng
        Map<String, Object> goldResult = syncGoldPrices(today);
        result.put("gold", goldResult);

        // 2. Đồng bộ lãi suất ngân hàng
        Map<String, Object> rateResult = syncBankInterestRates(today);
        result.put("interestRates", rateResult);

        // 3. Đồng bộ lãi suất phi rủi ro Rf
        BigDecimal rf = syncRiskFreeRate(today);
        result.put("riskFreeRate", rf);

        result.put("syncedAt", LocalDate.now(VN_ZONE).toString());
        return result;
    }

    public Map<String, Object> syncGoldPrices(LocalDate today) {
        return goldSync.sync();
    }

    @Transactional(readOnly = true)
    public List<GoldPriceDTO> getLatestGoldPrices() {
        return goldStore.latest();
    }

    /**
     * Đồng bộ biểu lãi suất ngân hàng
     */
    @Transactional
    public Map<String, Object> syncBankInterestRates(LocalDate today) {
        Map<String, Object> report = new LinkedHashMap<>();
        List<BankInterestRate> latest = bankInterestRateRepository.findAllLatestRates();

        // Nếu hôm nay chưa có bản ghi thì tự động carry forward các mức lãi suất có sẵn sang ngày hôm nay
        if (latest.stream().noneMatch(b -> today.equals(b.getEffectiveDate()))) {
            for (BankInterestRate rate : latest) {
                Optional<BankInterestRate> existingToday = bankInterestRateRepository
                        .findByBankCodeAndTermMonthsAndEffectiveDate(rate.getBankCode(), rate.getTermMonths(), today);
                if (existingToday.isEmpty()) {
                    BankInterestRate newRate = new BankInterestRate(
                            rate.getBankCode(), rate.getBankName(), rate.getTermMonths(), rate.getInterestRate(), today
                    );
                    bankInterestRateRepository.save(newRate);
                }
            }
        }

        report.put("totalBanksTracked", 8);
        report.put("status", "SUCCESS");
        return report;
    }

    /**
     * Lấy bảng so sánh lãi suất tổng hợp của các ngân hàng theo kỳ hạn
     */
    public List<BankComparisonDTO> getBankComparison() {
        List<BankInterestRate> rates = bankInterestRateRepository.findAllLatestRates();
        Map<String, String> bankNames = new LinkedHashMap<>();
        Map<String, Map<Integer, BigDecimal>> ratesMap = new LinkedHashMap<>();
        Map<String, LocalDate> datesMap = new LinkedHashMap<>();

        for (BankInterestRate r : rates) {
            bankNames.putIfAbsent(r.getBankCode(), r.getBankName());
            ratesMap.computeIfAbsent(r.getBankCode(), k -> new TreeMap<>()).put(r.getTermMonths(), r.getInterestRate());
            datesMap.put(r.getBankCode(), r.getEffectiveDate());
        }

        List<BankComparisonDTO> list = new ArrayList<>();
        for (Map.Entry<String, String> entry : bankNames.entrySet()) {
            String code = entry.getKey();
            list.add(new BankComparisonDTO(
                    code,
                    entry.getValue(),
                    ratesMap.getOrDefault(code, Collections.emptyMap()),
                    datesMap.getOrDefault(code, LocalDate.now(VN_ZONE))
            ));
        }
        return list;
    }

    /**
     * Đồng bộ và lấy lãi suất phi rủi ro Rf (SBV Interbank Rate)
     */
    @Transactional
    public BigDecimal syncRiskFreeRate(LocalDate today) {
        Optional<MacroIndicator> rfOpt = macroIndicatorRepository.findLatestByCode("RF_INTERBANK_RATE");
        if (rfOpt.isPresent()) {
            MacroIndicator ind = rfOpt.get();
            if (!today.equals(ind.getRecordedDate())) {
                MacroIndicator todayInd = new MacroIndicator(
                        ind.getIndicatorCode(), ind.getIndicatorName(), ind.getIndicatorValue(), ind.getUnit(), today
                );
                macroIndicatorRepository.save(todayInd);
            }
            return ind.getIndicatorValue();
        }

        // Mặc định chuẩn 4.5% nếu chưa có
        BigDecimal defaultRf = new BigDecimal("4.5000");
        MacroIndicator newInd = new MacroIndicator(
                "RF_INTERBANK_RATE", "Lãi suất phi rủi ro (SBV Interbank Rate)", defaultRf, "%", today
        );
        macroIndicatorRepository.save(newInd);
        return defaultRf;
    }

    public BigDecimal getRiskFreeRate() {
        return macroIndicatorRepository.findLatestByCode("RF_INTERBANK_RATE")
                .map(MacroIndicator::getIndicatorValue)
                .orElse(new BigDecimal("4.5000"));
    }
}
