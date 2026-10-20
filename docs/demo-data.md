# Bộ dữ liệu kiểm thử

Đã nạp sẵn vào database local, với ba tài khoản riêng:

| Tên đăng nhập | Mật khẩu | Kịch bản |
|---|---|---|
| `demo_balanced` | `Demo@123456` | Danh mục gần mục tiêu phân bổ |
| `demo_growth` | `Demo@123456` | Cổ phiếu chiếm tỷ trọng cao, có độ lệch để thử tái cân bằng |
| `demo_defensive` | `Demo@123456` | Thiên về vàng và tiết kiệm |

Mỗi tài khoản có 287 snapshot trong 400 ngày lịch, 169–206 giao dịch, 12 mã cổ phiếu và vàng, 5 sổ tiết kiệm (có sổ đã tất toán và sổ đang hoạt động), 6 mục tiêu tích lũy và 8 tài liệu riêng cho Copilot. Có các sự kiện nạp vốn định kỳ, mua/bán lô 100, phí giao dịch, cổ tức tiền mặt, mở/tất toán tiết kiệm.

Vào **Tổng quan → 3M/1Y/Tất cả** để xem đường NAV và chỉ số rủi ro; thử Sổ giao dịch, Sổ tiết kiệm, Tối ưu danh mục và Kho tri thức. Tài khoản demo có thông báo trên giao diện. Dự báo ML/TAA vẫn tuân thủ cấu hình của hệ thống; dữ liệu demo không chứng minh mô hình hiệu quả.

## Nguồn và giới hạn

- Giao dịch và lịch sử NAV là **mô phỏng kiểm thử**, không phải hoạt động đầu tư thực tế. Snapshot mang `snapshot_source='DEMO'`; báo cáo hiệu suất trả `dataKind='DEMO'`.
- Giá cổ phiếu/VNINDEX lấy từ CSV trong `ml/data/raw` và giá đang có trong DB. Chỉ thêm ngày còn thiếu, không ghi đè báo giá hiện có. CSV dùng giá đóng cửa từ nguồn sẵn có; trộn nguồn có thể khác điều chỉnh cổ tức/chia tách. Không dùng bộ lịch sử đã nhập này làm bằng chứng ML ngoài mẫu nếu chưa kiểm tra chất lượng nguồn giá.
- Chưa có chuỗi SJC lịch sử đầy đủ: phần vàng của mô phỏng dùng **giá SJC cố định** tại lúc tạo bộ dữ liệu. Không sinh giá vàng lịch sử giả trong bảng market_prices.
- Định giá dùng giá gần nhất trước hoặc trong ngày; ngày thiếu giá giữ giá trước đó. Tiền tiết kiệm trong NAV dùng gốc, phù hợp engine hiện tại; lãi được ghi nhận khi tất toán.
- Bút toán tài sản lưu số lượng, bút toán ví lưu VND, theo quy ước hiện có. Không cộng số lượng cổ phiếu trực tiếp với VND để kiểm tra cân bằng.
- Tài khoản người dùng có sẵn, số dư và giao dịch của họ được giữ nguyên. Script không reset, không xóa dữ liệu, không thay mật khẩu tài khoản có sẵn.

## Tạo lại trên database khác / chạy bổ sung

Chạy từ thư mục gốc, cần Docker container PostgreSQL và Python có bcrypt:

```sh
python3 scripts/seed_demo_data.py --output /tmp/equifolio-demo-preview.sql
python3 scripts/seed_demo_data.py --apply
```

Tùy chọn `--container` và `--database` đổi nơi nạp. Không truyền `--apply` chỉ tạo kế hoạch/SQL, không ghi DB. Toàn bộ lần nạp nằm trong một transaction có advisory lock. Các tên tài khoản demo đã tồn tại được **bỏ qua**, không ghi đè dữ liệu bạn đã thử trên chúng. Dữ liệu thị trường chèn theo khóa `(ticker, trade_date)` và bỏ qua hàng có sẵn. Không có tùy chọn reset tự động.

Ngày bắt đầu/kết thúc theo ngày chạy script; số lượng cụ thể có thể thay đổi do ngày trong tuần và giá hiện hành. Mật khẩu demo là mật khẩu công khai chỉ dành cho local test.
