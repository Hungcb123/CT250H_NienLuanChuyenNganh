-- ============================================================================
-- V2__seed_initial_data.sql
-- Initial Seed Data: Assets, Market Prices, Demo User & Target Portfolio
-- ============================================================================

-- 1. Khởi tạo danh mục tài sản hợp lệ
INSERT INTO assets (ticker, name, asset_class) VALUES
('VND', 'Tiền mặt Việt Nam Đồng', 'CASH'),
('EQUITY', 'Tài khoản Vốn chủ sở hữu', 'CASH'),
('HPG', 'CTCP Tập đoàn Hòa Phát', 'STOCK'),
('TCB', 'Ngân hàng TMCP Kỹ Thương Việt Nam', 'STOCK'),
('FPT', 'CTCP FPT', 'STOCK'),
('VNM', 'CTCP Sữa Việt Nam (Vinamilk)', 'STOCK'),
('GOLD_SJC', 'Vàng miếng SJC 999.9 (Chỉ)', 'GOLD'),
('GOLD_RING_9999', 'Vàng nhẫn tròn trơn 9999 (Chỉ)', 'GOLD')
ON CONFLICT (ticker) DO NOTHING;

-- 2. Giá thị trường mẫu (Đơn vị: VND)
INSERT INTO market_prices (ticker, price, trade_date) VALUES
('VND', 1.0000, CURRENT_DATE),
('HPG', 28500.0000, CURRENT_DATE),
('TCB', 24200.0000, CURRENT_DATE),
('FPT', 134000.0000, CURRENT_DATE),
('VNM', 68000.0000, CURRENT_DATE),
('GOLD_SJC', 8400000.0000, CURRENT_DATE),
('GOLD_RING_9999', 8250000.0000, CURRENT_DATE)
ON CONFLICT (ticker, trade_date) DO NOTHING;

-- 3. Người dùng mẫu (Demo User)
INSERT INTO users (id, username, email, password_hash, risk_score, risk_aversion_lambda, risk_profile) VALUES
(1, 'alex_nguyen', 'alex.nguyen@equifolio.vn', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 63, 4.33, 'BALANCED')
ON CONFLICT (id) DO NOTHING;

-- Đồng bộ sequence cho bảng users
SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));

-- 4. Tỷ trọng danh mục mục tiêu ban đầu của Demo User (SAA Baseline: 35% Cổ phiếu, 35% Vàng, 30% Tiết kiệm/Tiền mặt)
INSERT INTO portfolio_targets (user_id, asset_class, target_weight) VALUES
(1, 'STOCK', 0.3500),
(1, 'GOLD', 0.3500),
(1, 'CASH_SAVINGS', 0.3000)
ON CONFLICT (user_id, asset_class) DO NOTHING;

-- 5. Tài khoản mẫu trong Sổ cái cho Demo User
INSERT INTO accounts (user_id, account_code, asset_type, balance, version) VALUES
(1, 'VND_WALLET', 'VND', 45000000.0000, 0),
(1, 'EQUITY_CAPITAL', 'VND', 348720000.0000, 0),
(1, 'STOCK_HPG', 'HPG', 4000.0000, 0),       -- 4.000 cp HPG x 28.500 = 114.000.000
(1, 'STOCK_TCB', 'TCB', 3000.0000, 0),       -- 3.000 cp TCB x 24.200 = 72.600.000
(1, 'GOLD_SJC', 'GOLD_SJC', 6.0000, 0),      -- 6 chỉ SJC x 8.400.000 = 50.400.000
(1, 'SAVINGS_VCB_01', 'VND', 66720000.0000, 0) -- 66.720.000 gửi tiết kiệm Vietcombank
ON CONFLICT (user_id, account_code) DO NOTHING;

-- 6. Sổ tiền gửi tiết kiệm mẫu
INSERT INTO savings_deposits (user_id, account_id, bank_name, principal_amount, interest_rate, term_months, start_date, maturity_date, auto_rollover, accrued_interest, status) VALUES
(1, (SELECT id FROM accounts WHERE user_id = 1 AND account_code = 'SAVINGS_VCB_01'), 'Vietcombank', 66720000.0000, 5.50, 6, CURRENT_DATE - INTERVAL '60 days', CURRENT_DATE + INTERVAL '120 days', TRUE, 603254.0000, 'ACTIVE')
ON CONFLICT DO NOTHING;

-- 7. Nạp sẵn vài trích đoạn cẩm nang tài chính vào vector_store (hỗ trợ Hybrid Search)
INSERT INTO vector_store (content, metadata) VALUES
('Quy tắc khớp lệnh cổ phiếu sàn HOSE: Khối lượng giao dịch khớp lệnh bắt buộc là bội số của lô chẵn 100 cổ phiếu. Các lệnh lẻ dưới 100 cổ phiếu không được phép đặt trên bảng điện tử thông thường.', '{"topic": "HOSE_RULES", "asset": "STOCK"}'),
('Chiến lược phòng thủ bằng Vàng vật chất: Vàng miếng SJC có tính thanh khoản cao và khả năng bảo vệ tài sản trước rủi ro lạm phát hoặc khi thị trường cổ phiếu bước vào pha suy thoái (Risk-Off). Khi tỷ lệ Gold/VN-Index tăng cao, khuyến nghị tăng tỷ trọng Vàng.', '{"topic": "GOLD_HEDGING", "asset": "GOLD"}'),
('Nguyên tắc gửi tiết kiệm ngân hàng và Lãi suất phi rủi ro: Tiền gửi tiết kiệm kỳ hạn đóng vai trò là mốc an toàn cơ bản (Rf). Khi đáo hạn bật auto_rollover, tiền lãi nhập vào tiền gốc để tự động quay vòng chu kỳ mới, hiện thực hóa sức mạnh của lãi suất kép.', '{"topic": "SAVINGS_PRINCIPLE", "asset": "SAVINGS"}'),
('Quy tắc phân bổ tài sản 50/30/20 và Quỹ khẩn cấp: Trước khi phân bổ vốn lớn vào các tài sản biến động cao như Cổ phiếu, nhà đầu tư cần duy trì một quỹ dự phòng khẩn cấp tối thiểu tương đương 3 đến 6 tháng chi phí sinh hoạt gửi ở các kênh thanh khoản cao.', '{"topic": "ASSET_ALLOCATION", "asset": "CASH"}')
ON CONFLICT DO NOTHING;
