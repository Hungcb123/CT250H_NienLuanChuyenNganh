# Dữ liệu mô phỏng để kiểm thử

Ba tài khoản có lịch sử từ **12/08/2024 đến 19/10/2026**, mỗi tài khoản 571
snapshot ngày làm việc. Mật khẩu dùng cho môi trường test: `Demo@123456`.

| Tài khoản | Kịch bản | Giao dịch ban đầu |
|---|---|---:|
| `demo_balanced_extended` | Cân bằng, cổ phiếu/vàng/tiết kiệm/tiền mặt | 369 |
| `demo_growth_extended` | Nhiều cổ phiếu, độ lệch lớn so với SAA | 403 |
| `demo_defensive_extended` | Nhiều vàng và tiết kiệm | 312 |

Mỗi tài khoản có 5 sổ tiết kiệm (gồm đã tất toán và đang hoạt động), 6 mục tiêu
và 8 tài liệu mẫu cho Copilot. Có mua/bán lô 100 cổ phiếu, nạp vốn định kỳ,
cổ tức tiền mặt, tất toán và tái cân bằng. Dùng tab Tổng quan để thử các mốc
1W, 1M, 3M, YTD, 1Y và Tất cả; Sổ giao dịch để xem sổ cái.

Đăng xuất tài khoản hiện tại rồi đăng nhập một trong ba tài khoản trên.
Bộ demo có dữ liệu riêng; lịch sử của tài khoản đang dùng không tự kéo dài.
Các snapshot được đánh dấu `DEMO`; API hiệu suất ghi rõ dữ liệu mô phỏng.
Đã kiểm tra API: 1W = 6, 1M = 21, 3M = 66, YTD = 208, 1Y = 261,
Tất cả = 571 điểm. Cả ba bộ đều đạt `ALL_ACID_INVARIANTS_PASSED` sau khi
đối soát giao dịch và số dư. Script lưu giá trị VND tại thời điểm ghi sổ,
tách phí/thuế vào `TRADING_COSTS`, dùng số dư âm cho vốn và thu nhập.
Giá cổ phiếu/VNINDEX lấy từ CSV và dữ liệu đã có trong DB. Vàng SJC dùng giá
giả định cố định trong quá trình mô phỏng, không phải lịch sử SJC thực tế.
Bộ dữ liệu này phục vụ kiểm thử chức năng, không đánh giá hiệu quả đầu tư.

Để tạo lại trên DB local mới:

```bash
python3 scripts/seed_demo_data.py --extended --output /tmp/demo-extended.sql
python3 scripts/seed_demo_data.py --extended --apply
```

Mặc định dùng container `equifolio-postgres`, database `equifolio`; có thể đổi
bằng `--container` và `--database`. Script chạy trong một transaction, bỏ qua
tài khoản đã tồn tại và không ghi đè giá đã có. Tài khoản demo cũ vẫn được giữ.

## Tăng trưởng, phần cổ phiếu chỉ dùng ETF — ba năm

- Tài khoản: `demo_etf_growth_3y`; mật khẩu test: `Demo@123456`.
- Hồ sơ `GROWTH`, điểm 85, λ = 2.35 theo công thức trong `ProfileService`.
- SAA chuẩn của hồ sơ: **ETF 60%, vàng 20%, tiết kiệm 15%, tiền mặt 5%**.
  ETF chiếm 100% phần cổ phiếu; không có cổ phiếu riêng lẻ. Không phải danh mục
  100% NAV đầu tư ETF. Lưu sẵn lựa chọn ETF và chế độ SAA.
- 745 snapshot từ **19/10/2023 đến 19/10/2026**, 154 giao dịch mô phỏng.
- Vốn đầu 10 tỷ, nạp thêm 50 triệu vào phiên đầu mỗi tháng, tái cân bằng theo
  lô ETF 100 và đơn vị vàng nguyên. Tỷ trọng nắm giữ có sai số làm tròn nhỏ.
- ETF `E1VFVN30` và VNINDEX tải từ DNSE theo từng đoạn 90 ngày; ETF quy đổi
  giá nghìn đồng sang VND. Chỉ tạo snapshot cho phiên có đủ cả hai nguồn.
  Bỏ ngày 12/08/2024 vì DNSE thiếu giá VNINDEX; không điền hoặc bịa giá.
- **Giới hạn mô phỏng:** giá ETF là giá đóng cửa chưa điều chỉnh, không tự tạo
  cổ tức ETF; giá SJC cố định 14.310.000 đ/chỉ, lãi tiết kiệm giả định 5.5%/năm,
  tất toán trước hạn giả định 0.3%/năm. Tiết kiệm quay vòng ba tháng; cuối kỳ
  tất toán sổ đang mở và phân bổ lại. Phí/thuế theo quy tắc mô phỏng của app.
  Đây không phải lịch sử giao dịch thực hay backtest có toàn bộ giá tài sản thực.

Tái tạo trên DB local đã migrate đến V11:

```bash
python3 scripts/seed_etf_growth_3y.py --output /tmp/etf-growth-3y.sql
python3 scripts/seed_etf_growth_3y.py --apply
```

Nguồn, checksum và giả định lưu trong `ml/data/live/demo_etf_growth_3y/`:
`manifest.json`, hai CSV và `portfolio_summary.json`. Tài khoản đã tồn tại
được bỏ qua, giá đã có không bị ghi đè. Bộ nguồn cache gắn với kỳ ba năm cụ thể;
muốn chạy kỳ khác dùng `--data-dir` khác.
