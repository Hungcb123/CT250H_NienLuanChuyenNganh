-- V4: Cập nhật giá thị trường Vàng SJC và Vàng nhẫn 9999 sát thực tế 2026
-- Giá Vàng miếng SJC: 8.950.000 đ/chỉ (tương đương 89.500.000 đ/lượng)
-- Giá Vàng nhẫn 9999: 8.800.000 đ/chỉ (tương đương 88.000.000 đ/lượng)

INSERT INTO market_prices (ticker, price, trade_date)
VALUES ('GOLD_SJC', 8950000.0000, CURRENT_DATE)
ON CONFLICT (ticker, trade_date) DO UPDATE SET price = 8950000.0000;

INSERT INTO market_prices (ticker, price, trade_date)
VALUES ('GOLD_RING_9999', 8800000.0000, CURRENT_DATE)
ON CONFLICT (ticker, trade_date) DO UPDATE SET price = 8800000.0000;
