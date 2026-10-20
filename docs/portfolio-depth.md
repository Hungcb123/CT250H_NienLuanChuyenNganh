# Phát triển sáu phần phân tích danh mục

## Kết quả kiểm tra ML ban đầu

Hai ONNX nhận `[N,12]`; Java gửi 14 features, sai cả thứ tự và định nghĩa. Lỗi suy luận bị thay bằng heuristic RSI/SMA với confidence 60%. Bộ đọc xác suất cũng giả định `List<Map>` trong khi ONNX Runtime Java trả các phần tử `OnnxMap`. Vì vậy không thể coi các tín hiệu cũ là đầu ra ML đã được xác minh.

Model vàng học trên GC quốc tế, không đại diện trực tiếp cho SJC/VND. Runtime mới kiểm tra ticker trong metadata và từ chối áp GC vào SJC. Không dùng ETF thay VNINDEX nếu thiếu dữ liệu.

## Hành vi sau thay đổi

1. **Markowitz từ dữ liệu:** `/api/v1/research/optimize?tickers=FPT,HPG,TCB&lambda=5`. Cần 61 ngày giá chung trở lên, giá mới trong 7 ngày, tối đa 252 khoảng giá. Ước lượng mean/covariance, giải long-only fully invested bằng projected gradient, có ridge nhỏ; trả nghiệm cho λ=1–10. Đây là phân tích theo mã, chưa tự thay SAA theo lớp tài sản hay đặt lệnh. Chỉ dùng ticker có lịch sử phù hợp; lãi suất tiết kiệm không được giả làm chuỗi giá cổ phiếu.
2. **Hợp đồng ML:** `close-v1` gồm 12 features tính từ tối đa 120 giá đóng cửa và tối thiểu 60 giá. Python và Java dùng cùng công thức; fixture kiểm tra parity. Metadata ONNX chứa version, thứ tự features, ticker, horizon và ngày kết thúc train. Thiếu model/dữ liệu, giá quá cũ, NaN, sai schema hoặc confidence <55% trả signal/confidence bằng 0 và trạng thái `UNAVAILABLE_*`. Xác suất nhãn chưa được calibration, không gọi đó là xác suất chiến lược sinh lời.
3. **Đánh giá/backtest:** bốn expanding folds, purge 20 mẫu ở mỗi ranh giới cho nhãn T+20. So F1-macro với majority baseline và báo MCC. Model đóng gói là model của fold cuối, chưa refit lên holdout. Backtest dùng dự báo ngoài mẫu từ từng fold, tín hiệu tại close(t), giao dịch tại close(t+1), hưởng lợi suất close(t+1) → close(t+2), giữ SAA khi xác suất dưới 55%. So mua giữ, SAA 35% cổ phiếu, TAA ±15 điểm %. Tính turnover trên tỷ trọng đã drift và phí 0,15%/turnover, kể cả vào vị thế ban đầu. Tiền mặt lãi 0; không mô phỏng vàng, thuế, trượt giá, lô chẵn, khớp lệnh trong ngày hay khả năng mua trực tiếp VNINDEX. Đây là mô phỏng nghiên cứu, không phải bản sao toàn bộ engine giao dịch. Có độ trễ thực thi một phiên; vẫn cần dữ liệu khớp lệnh để đánh giá trượt giá thực tế.
4. **Copilot:** nạp văn bản → chia đoạn 1100 ký tự, overlap 200 → full-text không dấu hoặc embedding + RRF (`k=60`) → trả tối đa 5 nguồn có UUID, tên, nguồn, số đoạn. Tài liệu riêng theo user, có kiểm thử chống đọc chéo tài khoản. Các tài liệu seed không có owner là tài liệu chung. Model embedding phải giữ ổn định; đổi model cần nạp lại tài liệu. Prompt yêu cầu dẫn UUID và coi nội dung tham khảo là dữ liệu, không phải chỉ thị. Chưa có bộ đo groundedness tự động hoặc lưu hội thoại vào DB.
5. **Hiệu suất:** liên kết Modified Dietz, loại vốn nạp/rút qua bút toán `EQUITY_CAPITAL`, XIRR theo ngày thực, drawdown trên chỉ số tăng trưởng đã điều chỉnh dòng tiền. Giả định nạp/rút cuối ngày; không phải TWR chính xác trong ngày. Annual return theo thời gian lịch, volatility/Sharpe trên lợi suất chuẩn hóa ngày lịch, annualize 365,25. Snapshot thưa làm mượt volatility; cần đủ snapshot quan sát. Chênh lệch với VNINDEX không phải Jensen alpha. Không nội suy NAV bằng sin/cos nữa. V7 giữ dữ liệu cũ dưới nhãn `LEGACY_UNVERIFIED`; chỉ `OBSERVED` được dùng để tính. NAV quan sát vẫn phụ thuộc chất lượng giá thị trường cache.
6. **Mục tiêu tích lũy:** CRUD `/api/v1/goals`, kiểm tra chủ sở hữu và optimistic version. Lưu vốn dành riêng, mức góp, số tiền đích, ngày hoàn thành, lãi suất giả định; tính FV, thiếu hụt và mức góp cần thiết. Góp cuối tháng, đếm số tháng theo YearMonth; mục tiêu trong tháng hiện tại không có kỳ góp. Vốn do người dùng khai báo, chưa tự trích NAV hoặc khóa tiền giữa nhiều mục tiêu.

## Truy cập giao diện

**Tối ưu danh mục** chứa sáu mục phân tích. Minh họa Markowitz cũ được giữ trong phần mở rộng, ghi rõ tham số giả định. Màn hình TAA mở kế hoạch tái cân bằng để xác nhận, không ghi cứng tỷ trọng 50/20/20/10 vào SAA. Các API lịch sử/rủi ro không trả số liệu demo khi lỗi. Có điều hướng chọn mục trên màn hình nhỏ.

## Huấn luyện và cấu hình

Chạy tại thư mục gốc:

```sh
python3 -m pip install -r ml/requirements.txt
python3 ml/train_regime_model.py
python3 -m unittest discover -s ml -p 'test_*.py'
mvn -f backend/pom.xml test
npm --prefix frontend run build
```

Không sinh dữ liệu giả nếu CSV thiếu. Pipeline đọc `ml/data/raw/VNINDEX.csv` và `GC.csv`, kiểm tra giá dương/hữu hạn và ngày không vượt hiện tại. Báo cáo ở `ml/reports/`, bản dùng API nằm trong resources/models. Dữ liệu hiện tại kết thúc 2026-10-01; file CSV cần được cập nhật để thực nghiệm giai đoạn mới. Không tự động tái huấn luyện trong production.

`ML_TAA_ENABLED` mặc định `false`: kết quả ngoài mẫu hiện tại không hỗ trợ bật TAA mặc định. Trong cấu hình mô phỏng, lợi suất TAA khoảng 7,88%, SAA khoảng 13,54%, mua giữ khoảng 37,29%; rủi ro và tỷ trọng khác nhau nên không kết luận chỉ từ lợi suất. Bật opt-in chỉ thay hành vi TAA, không chứng minh model có lợi thế.

Embedding tùy chọn, endpoint tương thích request/response embeddings:

```text
EMBEDDING_URL=http://your-provider/v1/embeddings
EMBEDDING_MODEL=your-1536-dimensional-model
EMBEDDING_API_KEY=...
```

Không cấu hình URL: `FULL_TEXT`, không giả là semantic search. Có URL: provider phải trả vector 1536 chiều; lỗi search chuyển full-text có nhãn, lỗi ingest hủy transaction. Không gửi tài liệu ra provider nếu chưa cấu hình. Nguồn là nhãn/URL, hệ thống không tự tải trang web đó.

Khởi động lại backend để Flyway áp V6/V7 và nạp model mới. V7 không xóa snapshot cũ nhưng loại chúng khỏi phân tích vì không thể phân biệt hàng nội suy cũ với hàng quan sát cũ một cách đáng tin.

## Kiểm thử database/API độc lập

Hai integration tests chỉ chạy khi `EQUIFOLIO_TEST_DB` chứa tên `equifolio_validation`. Dùng database tạm riêng, không dùng database ứng dụng:

```sh
EQUIFOLIO_TEST_DB=jdbc:postgresql://localhost:5432/equifolio_validation_example \
  mvn -f backend/pom.xml test
```

User mặc định postgres; mật khẩu từ `EQUIFOLIO_TEST_PASSWORD` (mặc định postgres cho local). Database phải tồn tại. Test chạy migration, truy xuất tiếng Việt, pgvector/RRF bằng embedding server cục bộ, cô lập tài khoản, mục tiêu/version và xác thực JWT/API. Spring context thay các dịch vụ gọi mạng bằng mock. Browser validation dùng API fixture để kiểm tra sáu mục trên desktop/mobile, tách khỏi kiểm thử backend thật.
