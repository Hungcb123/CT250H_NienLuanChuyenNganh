package com.equifolio.ledger;

import jakarta.validation.constraints.*;
import java.math.BigDecimal;

public record CashWithdrawalRequest(
        @NotNull @DecimalMin("1") @Digits(integer = 15, fraction = 0) BigDecimal amount,
        @Size(max = 255) String description) {}
