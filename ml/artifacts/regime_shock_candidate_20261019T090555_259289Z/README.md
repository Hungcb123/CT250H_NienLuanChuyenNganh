# Native shock_shrink research snapshot

Đã lưu bộ model chạy từ đặc trưng thị trường, không cần CSV dự đoán để suy luận:

- 2 LightGBM classifier: trend/information và risk.
- 90 LightGBM quantile regressors: 5 seed × 2 mục tiêu × 9 phân vị.
- 8 Random Forest: hai forest thường, hai forest mean/magnitude, bốn forest có đặc trưng shock.
- Hai kho analog compact/full, các mẫu lợi suất raw/normalized, median/IQR và mẫu lợi suất trong lá của forest.

Mốc dữ liệu và huấn luyện: **01/10/2026**. Mọi nhãn huấn luyện đều kết thúc trước mốc này. Cấu hình đặc trưng và fusion giữ cố định lựa chọn từ fold lịch sử cuối, không tìm cấu hình mới dựa vào điểm đã xem. Đây là snapshot lịch sử tạo ngày 19/10; preview không phải dự báo đã được ghi nhận từ ngày 01/10 hay mẫu kiểm chứng tương lai.

Bộ tạo đặc trưng giữ các phiên chưa có nhãn ở cuối dữ liệu. Toàn bộ giá trị đối chiếu với các bảng đặc trưng nghiên cứu khớp với sai số bằng 0. `preview.json` là kết quả cold start: chưa có EMA của phiên trước, nên không được đồng nhất với chuỗi dự đoán có trạng thái liên tục.

Chạy preview từ dữ liệu hiện có:

```bash
python3 ml/predict_regime_shock.py \
  --bundle ml/artifacts/regime_shock_candidate_20261019T090555_259289Z/native \
  --parameters 0.75 0.75 1.5
```

Thêm `--require-fresh` để từ chối đầu vào cũ quá 4 ngày lịch. Với dữ liệu hiện tại, lệnh phải từ chối vì ngày cuối là 01/10, cách ngày tạo snapshot 18 ngày. Cờ này là kiểm tra tuổi dữ liệu theo ngày, chưa thay thế việc xác minh lịch nghỉ sàn, độ trễ nguồn và thời điểm hoàn tất phiên.

Có thể thêm `--state-file /path/to/state.json` để lưu EMA sau một preview thành công. Ngày liền trước phải là phiên liền trước trên lịch VNINDEX, không phải ngày liền trước trên lịch dương. Phiên lặp hoặc thứ tự ngược bị từ chối; thiếu một phiên dự đoán làm EMA reset. CLI dùng cho nghiên cứu cục bộ, chưa có khóa đồng thời hay ledger phát hành bất biến cho phục vụ nhiều yêu cầu.

Các điểm số là score quyết định đã cân bằng lớp. `calibrated_probability` là null. Không hiển thị 0,51 thành “51% khả năng dự đoán đúng”. Macro F1 51,37% được đo trên chuỗi historical development với refit định kỳ, không phải điểm kiểm chứng riêng của snapshot được fit ngày 01/10.

`contract.json` có công thức, nguồn, cấu hình và trạng thái chưa chấp nhận triển khai; `checksums.json` kiểm tra các payload lúc xuất. Bộ native có Python joblib: chỉ nạp bundle tin cậy do pipeline này tạo, không nhận file model upload từ người dùng.

Chưa triển khai lên web. Cần dữ liệu mới, quy trình refit và lựa chọn cấu hình cho vận hành, ledger dự báo, đánh giá xác suất riêng và kết quả thực sự ngoài mẫu.
