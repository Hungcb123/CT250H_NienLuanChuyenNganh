package com.equifolio.optimizer;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.equifolio.ledger.*;
import com.equifolio.market.*;
import com.equifolio.profile.*;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class TaaPolicyTest {
  @Test
  void disabledByDefaultAndNeverAllocatesOverOneHundredPercent() {
    var ledger = mock(LedgerService.class);
    var targets = mock(PortfolioTargetRepository.class);
    var models = mock(OnnxRegimeService.class);
    var optimizer =
        new PortfolioOptimizerService(
            ledger,
            targets,
            mock(MarketService.class),
            mock(AccountRepository.class),
            mock(TransactionRepository.class),
            mock(UserRepository.class),
            mock(AssetRepository.class),
            models,
            mock(SavingsDepositRepository.class));
    BigDecimal weight = new BigDecimal("0.35");
    BigDecimal unchanged =
        ReflectionTestUtils.invokeMethod(
            optimizer,
            "calculateTaaWeight",
            weight,
            new RegimePrediction(1, .9, "ONNX_BULLISH"),
            new BigDecimal("0.15"));
    assertEquals(0, weight.compareTo(unchanged));
    ReflectionTestUtils.setField(optimizer, "taaEnabled", true);
    var stock = new PortfolioTarget();
    stock.setAssetClass("STOCK");
    stock.setTargetWeight(new BigDecimal("0.05"));
    var gold = new PortfolioTarget();
    gold.setAssetClass("GOLD");
    gold.setTargetWeight(new BigDecimal("0.95"));
    when(targets.findByUserId(1L)).thenReturn(List.of(stock, gold));
    var valuation = new PortfolioValuationDTO();
    when(ledger.calculatePortfolioValuation(1L)).thenReturn(valuation);
    when(models.predictStockRegime()).thenReturn(new RegimePrediction(1, .9, "ONNX_BULLISH"));
    when(models.predictGoldRegime())
        .thenReturn(new RegimePrediction(0, 0, "UNAVAILABLE_GOLD_ASSET_MISMATCH"));
    var plan = optimizer.generateRebalancePlan(1L);
    BigDecimal sum =
        plan.getTaaTargets()
            .get("STOCK")
            .add(plan.getTaaTargets().get("GOLD"))
            .add(plan.getTaaTargets().get("CASH_SAVINGS"));
    assertEquals(0, BigDecimal.ONE.compareTo(sum));
  }
}
