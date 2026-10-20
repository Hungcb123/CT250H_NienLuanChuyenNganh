# Xuất model Python shock_shrink sang ONNX

`backend/src/main/resources/models/shock/shock_regime.onnx` chứa toàn bộ bộ trọng số
đã fit trong `regime_shock_candidate_20261019T090555_259289Z/native`: 2 classifier,
90 quantile regressor, 8 forest, mẫu lợi suất trong lá, kho analog, phép cân bằng
lớp, fusion và một bước EMA. Không train lại, không distillation hay quantization.
Số liệu parity và latency thực đo nằm trong `contract.json` cạnh model.

## Deploy web bằng Java, không cần Python

Backend mặc định dùng `ML_STOCK_MODEL=shock-onnx`. `NativeRegimeService` chuyển
request từ API/optimizer sang `EmbeddedRegimeService`; `ShockFeatures` tính đủ
45 feature từ bar thị trường, rồi `ShockOnnxModel` gọi ONNX Runtime ngay trong
JVM. Không gọi HTTP worker, không khởi chạy Python và không tự train trên server.
API/DTO hiện có được giữ để frontend, copilot và TAA dùng kết quả mới.

```bash
cd backend
mvn clean package
ML_STOCK_MODEL=shock-onnx REGIME_MANAGED=false java -jar target/equifolio-backend-1.0.0-SNAPSHOT.jar
```

Thiết lập `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` như backend
hiện tại. Flyway tự tạo bảng bar thị trường bằng migration V15. Model, contract
và lịch sử khởi tạo đã đóng trong JAR; không cần chép thư mục `ml/` lên server.
Khi dùng biến môi trường cũ, đổi `ML_STOCK_MODEL=native` thành `shock-onnx`.
Có thể build Docker tại repo root: `docker build -t equifolio-backend backend`.
Image chỉ có Java runtime; truyền cấu hình DB/ứng dụng lúc chạy container.

Java đồng bộ bar DNSE khi khởi động và mỗi 15 phút. Chỉ nhận phiên đã đóng cửa
sau 15:30 giờ Việt Nam; không nhận bar đang chạy, không điền phiên thiếu. Seed
là lịch sử đã duyệt; phần dữ liệu mới lưu append-only trong PostgreSQL. Bar đã
nhận mà bị nhà cung cấp sửa sẽ bị từ chối. Dịp nghỉ sàn chưa có lịch được xác
minh sẽ giữ trạng thái chưa sẵn sàng thay vì tự suy đoán lịch.

EMA và dự báo được lưu atomically ở `ml_regime_streams` / `ml_regime_predictions`.
Khóa DB bảo đảm nhiều request cùng phiên chỉ công bố một kết quả; restart trả
lại dự báo đã lưu. Thiếu một phiên dự báo sẽ reset EMA. Lần chuyển từ Python
sang ONNX tạo stream mới và cold start một lần, không sửa các dự báo Python cũ.

T+60/T+120 dùng hai baseline LightGBM thử nghiệm đã xuất ONNX, fit trên các nhãn
đã trưởng thành tại mốc 01/10/2026. Không phải ensemble T+20 và chưa có đánh giá
độc lập. Các model đóng băng không còn được Python refit mỗi ngày. Tất cả yêu
cầu cập nhật bộ trọng số sau 63 phiên kể từ mốc model: trả `REFIT_REQUIRED`
thay vì âm thầm dùng model cũ, Python hay classifier 12 feature.

`REGIME_ONNX_DIRECTORY` có thể trỏ đến `file:/duong-dan/bundle/` để nạp bộ model
khác đã duyệt, đủ cả ba horizon, seed và checksum; mặc định là classpath trong JAR.

Kiểm tra bản tích hợp:

```bash
cd backend
mvn -Dtest=ShockFeaturesTest,EmbeddedOnnxModelTest,ShockOnnxContractTest test
# DB test tạo và xóa schema riêng trong PostgreSQL được cung cấp:
EQUIFOLIO_ONNX_TEST_URL=jdbc:postgresql://localhost:5432/equifolio_validation \
  mvn -Dtest=EmbeddedRegimeDatabaseTest test
```

Xuất lại từ thư mục gốc, dùng thư mục đích mới:

```bash
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python3 ml/export_regime_shock_onnx.py \
  --bundle ml/artifacts/regime_shock_candidate_20261019T090555_259289Z/native \
  --output-dir ml/artifacts/regime_shock_onnx_new
python3 ml/prepare_onnx_deployment.py --source-dir ml/artifacts/regime_shock_onnx_new
python3 -m unittest discover -s ml -p test_export_regime_shock_onnx.py -v
cd backend
mvn -Dtest=ShockOnnxContractTest test
```

Exporter chỉ công bố thư mục đích sau khi kiểm tra thành công mọi dòng có đủ
feature hữu hạn trong snapshot, nhãn khớp tuyệt đối, sai số score <= 1e-5,
và chuỗi EMA. `parity_fixture.json` lưu kết quả tham chiếu từ Python cho kiểm thử
Java cold start và EMA liên tục. `checksums.json` kiểm tra toàn bộ payload.

## Hợp đồng suy luận

| Input | ONNX type | Shape | Ý nghĩa |
| --- | --- | --- | --- |
| `features` | double | `[N, 45]` | Thứ tự chính xác trong `contract.json.features` |
| `horizon_sigma` | double | `[N]` | Độ lệch chuẩn mẫu log return 20 phiên × sqrt(20), hữu hạn và > 0 |
| `parameters` | double | `[3]` | density weight, classifier temperature, density temperature |
| `previous_ema` | double | `[N, 3]` | EMA đã lưu, hoặc zeros khi cold start |
| `contiguous` | bool | scalar | Có EMA của đúng phiên thị trường liền trước hay không |

Các feature cây được cast float32 giống Python; analog, mẫu lợi suất và fusion
giữ double. `parameters` của snapshot là `[0.75, 0.75, 1.5]`. Chạy chuỗi thời
gian bằng từng phiên `N=1`; batch dùng cho các dòng/stream độc lập, cùng cờ
`contiguous`. Bộ nhớ batch tăng theo số dòng × số mẫu huấn luyện × số cây.

Output `class_scores` và `ema` có shape `[N, 3]`, thứ tự bearish, sideway, bullish.
`signal` có shape `[N]`, giá trị -1, 0, 1. Sáu output thành phần giúp chẩn đoán
parity. Score không phải xác suất đã hiệu chỉnh. Không áp ngưỡng confidence 0.55
của classifier cũ vào score này.

Ứng dụng gọi graph phải kiểm tra input, tuổi dữ liệu, cửa sổ refit 63 phiên,
phiên trùng/ngược thứ tự và phiên liền trước trên lịch thị trường. Chỉ lưu output
`ema` sau khi dự báo được chấp nhận. Cờ false reset EMA; không truyền NaN cho
`previous_ema` ngay cả khi reset. Graph không truy cập lịch hoặc database.

ONNX này có hợp đồng khác `backend/.../models/stock_regime.onnx` cũ (12 feature).
Luồng web mặc định đã dùng model mới qua bộ dựng 45 feature Java; classifier
12 feature chỉ còn dành cho chế độ cũ `ML_STOCK_MODEL=onnx` được chọn rõ ràng.

Parity chứng minh tính tương đương trên dữ liệu được kiểm tra, không chứng minh
mọi input tương lai đều khớp bit. Snapshot được fit tại mốc 01/10/2026; replay
các dòng trước mốc này phục vụ kiểm tra chuyển đổi, không phải đánh giá ngoài
mẫu. Latency đo trực tiếp hai engine trên cùng feature, không gồm feature
engineering, HTTP, khởi động session hoặc truy vấn database; không suy ra Java
nhanh hơn Python chỉ từ khác biệt ngôn ngữ.
