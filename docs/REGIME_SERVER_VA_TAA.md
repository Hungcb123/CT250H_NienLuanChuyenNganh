# Dự báo VNINDEX trên server và lựa chọn SAA/TAA

## Đã tích hợp gì?

Code backend mặc định chọn `ml.stock-model=native` cho VNINDEX. Java gọi worker Python chứa bộ100model `shock_shrink`; nhận đủ ba score, nhãn, ngày phiên và net score. Vàng giữ đường ONNX cũ. Không dùng ONNX cổ phiếu thay thế khi worker native lỗi.

```text
Frontend → Spring Boot → NativeRegimeService → Python worker
                                               ↓
                                     Native bundle100models
                                               ↓
                                  PostgreSQL prediction + EMA
                                               ↓
                          Java DirectionalTaaPolicy → target allocations
```

Tích hợp code không đồng nghĩa đã triển khai lên một máy chủ đang chạy. Backend mặc định tự khởi động worker Python và dừng worker do nó tạo khi backend tắt. TAA vẫn **tắt mặc định** vì chưa có bằng chứng nó luôn cải thiện kết quả danh mục.

## Chạy bằng bộ trọng số đã có

Cần môi trường ML đang chạy được `predict_regime_shock.py`, cùng PostgreSQL của ứng dụng. Bộ native kiểm tra phiên bản numpy/scipy/scikit-learn/lightgbm/joblib theo `bundle.json`.

1. Khởi động PostgreSQL như cấu hình ứng dụng hiện có. Từ thư mục `backend`, chạy:

   ```bash
   mvn spring-boot:run
   ```

   Flyway áp dụng các migration mới đến V10, tạo bảng dự báo và lựa chọn phân bổ. Không sửa dữ liệu giao dịch/danh mục hiện có. Backend toàn ứng dụng vẫn cần pgvector như các migration cũ.

2. Chuẩn bị Python **một lần** tại gốc repo:

   ```bash
   python3 -m pip install -r ml/requirements-regime-server.txt
   ```

   Nếu dùng virtualenv hoặc Windows, đặt `REGIME_PYTHON` thành đường dẫn executable Python của môi trường đã cài các gói trên. Bộ trọng số đã có phải còn ở repo.

3. Các lần sau chỉ cần PostgreSQL → backend → frontend (`cd frontend`, `npm run dev`). Backend tự khởi động `ml/serve_regime_shock.py`, truyền cấu hình DB đang dùng cho worker. Không cần terminal Python riêng. Log worker được nối vào console backend.

   Có thể chạy worker riêng bằng `python3 ml/serve_regime_shock.py` và đặt `REGIME_MANAGED=false`. Java không dừng worker bên ngoài. Nếu worker đặt trên máy khác, tự triển khai nó trên máy đó và cấu hình `REGIME_NATIVE_URL`.

## Tự cập nhật và dự báo mỗi phiên

- Khi startup, worker kiểm tra PostgreSQL trước. Nếu phiên cần dùng đã có kết quả của cùng policy/model thì trả lại bản đã lưu, **không tải lại API hoặc infer lại**.
- Nếu chưa có: lấy phiên weekday gần nhất đã đóng cửa, tải phần đuôi dữ liệu còn thiếu, tạo snapshot bất biến tại `ml/data/live/regime/`, tính feature, chạy model và lưu prediction/EMA trong một transaction.
- Giờ Việt Nam, trước **15:30** dùng phiên weekday trước; từ **15:30** dùng phiên hôm đó. Thứ Bảy/Chủ nhật dùng thứ Sáu. Worker kiểm tra mỗi phút nên không phụ thuộc giờ server được bật.
- Ví dụ dữ liệu có đến 01/10, bật server sau 15:30 ngày 19/10: lấy các phiên mới API trả về đến 19/10, chỉ dự báo phiên 19/10. Không chế dự báo cho các ngày server đã tắt. EMA reset khi thiếu predecessor theo contract hiện có.
- Khi cập nhật lỗi, giữ nguyên snapshot/kết quả đã commit và thử lại sau **15 phút**. Trong thời gian chờ, API không quảng cáo dự báo cũ là của phiên mới.
- `POST /v1/predict` mặc định **chỉ đọc cache PostgreSQL**; mở FE hoặc gọi API nhiều lần không chạy lại model. Khóa advisory PostgreSQL ngăn hai worker cùng cập nhật một stream.
- T+20 suy luận hằng ngày bằng bộ trọng số hiện có, không train lại. Baseline thử nghiệm T+60/T+120 được fit hằng ngày bằng nhãn đã đáo hạn. Không tự bật TAA và không đặt lệnh giao dịch.

Nguồn live: VNINDEX OHLCV, ETF E1VFVN30 và VN30 từ DNSE; VNMID/VNSML từ VND vì DNSE chart không hỗ trợ các symbol này; VIX từ Cboe. Giá ETF nhân 1.000 về VND, chỉ số giữ đơn vị điểm. Ngày API trả về là lịch tham chiếu; không tự tạo nến cho ngày nghỉ. Hôm nghỉ lễ weekday có thể chưa có dự báo mới, nhưng không ngăn nối dữ liệu vào phiên giao dịch tiếp theo.

Snapshot nghiên cứu và source receipt đã khóa được giữ nguyên. Feature live giữ công thức cũ nhưng dùng policy `dnse-append-close-v1` và hash code riêng; không gọi OHLCV DNSE một nguồn là consensus nhiều broker. Dữ liệu sửa lại trên phần live đã chấp nhận bị từ chối thay vì ghi đè. Hai chỉ số nhóm/VIX không khả dụng giữ missing theo cơ chế model, ghi tình trạng vào manifest; không lấy mã khác hoặc bfill để thay thế.

Kiểm tra worker:

```bash
curl http://127.0.0.1:8091/health
curl -X POST http://127.0.0.1:8091/v1/predict
```

`/health` báo model đã nạp và trường `daily` cho trạng thái cập nhật (`SYNCING`, `PREDICTING`, `READY`, lỗi). Chỉ model loaded chưa chứng minh dữ liệu/DB đã sẵn sàng. Dự báo thành công mới cần cả dữ liệu hợp lệ và transaction DB thành công.

API qua Spring Boot: **POST `/api/v1/research/native-regime/prediction`**, dùng xác thực JWT hiện có của ứng dụng. `/api/v1/research/models` và kế hoạch tái cân bằng cũng sử dụng kết quả native. Frontend không gọi trực tiếp worker.

## Cấu hình

| Biến | Mặc định / ý nghĩa |
|---|---|
| `ML_STOCK_MODEL` | `native`; chọn `onnx` chỉ khi chủ động quay lại đường cũ |
| `REGIME_MANAGED` | `true`; backend tự tạo worker local. `false` nếu dùng supervisor/worker riêng |
| `REGIME_PYTHON` | `python3`; đặt executable của môi trường ML trên máy chạy backend |
| `REGIME_WORKER_SCRIPT` | `../ml/serve_regime_shock.py`; có fallback khi chạy từ gốc repo |
| `REGIME_LIVE_DATA_DIR` | `ml/data/live/regime`; lưu snapshot live và pointer latest |
| `REGIME_RETRY_SECONDS` | `900`; thời gian thử lại sau lỗi cập nhật |
| `REGIME_DAILY_ENABLED` | `true` khi worker tự chạy; `false` chỉ cho chế độ kiểm tra thủ công. Worker do Java quản lý luôn bật daily |
| `REGIME_NATIVE_URL` | Java gọi `http://127.0.0.1:8091` |
| `REGIME_HOST`, `REGIME_PORT` | Worker bind `127.0.0.1`, port `8091` |
| `REGIME_API_TOKEN` | Shared token giữa Java/worker; bắt buộc nếu worker bind ngoài loopback |
| `REGIME_DATABASE_URL` | Ghi đè DSN; nếu không có, dùng các biến DB chung với backend |
| `REGIME_ARTIFACT` | Thư mục candidate, mặc định `ml/artifacts/regime_shock_candidate_20261019T090555_259289Z` |
| `REGIME_DATA_DIR` | Mặc định thư mục reviewed `brokers_2010_20261001_reviewed` |
| `REGIME_POLICY_VERSION` | `postgres-net-v1`; đổi có chủ đích để mở stream mới khi thay đổi quy tắc |
| `ML_TAA_ENABLED` | Cấu hình legacy; lựa chọn SAA/TAA theo tài khoản ở giao diện quyết định phân bổ hiện tại |

Nếu Java và worker ở hai container khác nhau, `REGIME_NATIVE_URL` phải trỏ đến hostname worker, không phải localhost của container Java. Worker ngoài loopback yêu cầu shared token. Đây là dịch vụ nội bộ, không mở trực tiếp ra Internet.

Không di chuyển chỉ riêng file JAR hoặc100file model rồi kỳ vọng worker tự chạy: worker cần candidate gồm `empirical.npz`/metadata, các module ML đã khóa và dữ liệu nguồn mà feature builder sử dụng. Các source receipt Python được xác minh theo đường dẫn tương đối của checkout, không phụ thuộc đường dẫn `/mnt/d/...` trên máy train. Các CSV dự đoán lịch sử là provenance, không phải đầu vào suy luận của worker.

## Vì sao hiện có thể báo không khả dụng?

Seed mặc định kết thúc **01/10/2026**; worker daily tự nối dữ liệu live khi startup. Trong lúc chưa đồng bộ xong hoặc API lỗi, `/v1/predict` trả HTTP 503 (`DAILY_UPDATE_PENDING`, `SYNCING`, `DAILY_UPDATE_FAILED`, `STALE_OR_INCOMPLETE_SESSION`...). Xem `daily` trong `/health` và log backend. Kết quả hiện hành chỉ có sau khi dữ liệu hoàn chỉnh và commit PostgreSQL thành công.

Chưa có lịch nghỉ sàn độc lập: ngày nghỉ lễ weekday có thể báo không khả dụng. Không lấy nến trong phiên, không dời cutoff để ép chạy, không sinh giá cho ngày API không cung cấp.

Ensemble T+20 chỉ được dùng từ mốc refit trở đi, tối đa63phiên theo lịch dữ liệu. Hết cửa sổ trả `REFIT_REQUIRED`; không áp model fit từ tương lai cho ngày cũ. Thay artifact/refit là thao tác riêng, không tự train theo từng request.

## Lưu EMA và tính idempotency

`ml_regime_streams` lưu policy, phiên cuối và state. `ml_regime_predictions` lưu ngày phiên, predecessor, fingerprint input/model, raw/EMA/final, kết quả API và thời điểm phát hành.

Stream key là SHA256 của policy: asset, mode, candidate, recipe, fusion parameters, phiên bản serving, code feature và policy/hash feature live khi chạy daily. Một phiên có khóa duy nhất `(stream_key, session_date)`.

Trong một transaction:

1. Tạo stream nếu chưa có; khóa stream bằng `SELECT ... FOR UPDATE`.
2. Nếu phiên đã phát hành và input/model/predecessor giống nhau, trả nguyên response cũ, kể cả `published_at`; không chạy inference hay cập nhật EMA lần nữa.
3. Nếu cùng phiên nhưng đầu vào/model khác, trả conflict, không ghi đè dự báo cũ. Muốn nghiên cứu bản sửa cần policy version khác, không sửa âm thầm.
4. Nếu là phiên mới đúng thứ tự, chạy model, tính EMA, ghi dự báo rồi cập nhật state trong cùng transaction.
5. Chỉ commit khi tất cả thành công. Lỗi model, dữ liệu hoặc DB phải rollback cả hai phần.

Thời điểm phát hành dùng `clock_timestamp()` sau khi tính score, tránh dùng thời điểm bắt đầu transaction như thể đã có dự báo trước đó. Không gọi inference nhiều lần để cập nhật EMA nhiều lần cho cùng ngày. Dữ liệu sửa không tự viết lại lịch sử đã phát hành.

EMA đúng theo bản nghiên cứu:

```text
EMA_t   = raw_t / 3 + 2 × EMA_(t−1) / 3
final_t = raw_t / 2 + EMA_t / 2
```

Lần đầu cold start, `EMA_t=raw_t`, trả `ema_reset=true`. Bỏ lỡ một phiên dự đoán thì reset ở phiên tiếp theo, giữ đúng contract đã kiểm tra; không tự nối state qua khoảng thiếu. Mode `historical` và `live` có stream khác nhau; không nhập state replay vào stream live.

`independent_prospective_prediction` hiện vẫn giữ false: có bản ghi bất biến chưa tự chứng nhận dữ liệu/vintage/timing đủ chuẩn cho nghiên cứu prospective. Các phép đánh giá sau phải dựa vào thời điểm phát hành thực sự.

## Chính sách net score cũ (đối chiếu nghiên cứu)

Công thức dưới đây thuộc chính sách nghiên cứu cũ. Luồng ứng dụng hiện tại dùng lựa chọn theo tài khoản và bước ±10 điểm % theo argmax, mô tả ở cuối tài liệu; nhãn đi ngang giữ SAA.

```text
net_score = final_bull − final_bear
Δw_stock  = net_score × 0.15
w_stock   = clamp(w_SAA + Δw_stock, 0, 1)
```

Java vẫn áp dụng ràng buộc tổng phân bổ không vượt100% với các lớp còn lại. Nếu TAA tắt hoặc dự báo không khả dụng, giữ anchor SAA. Gold vẫn dùng chính sách ONNX cũ.

Ví dụ `[0.30, 0.34, 0.36]`: net=+0,06. Anchor35% thành35,9% khi TAA bật, tức tăng0,9 **điểm phần trăm**. Không phải tăng9% hay6% NAV.

Nhãn argmax vẫn dùng để hiển thị/phân loại. Nhãn sideway có thể đi cùng net khác0: chính sách phân bổ dùng toàn vector nên vẫn có thể nghiêng nhẹ tăng/giảm. Đây là thay đổi chính sách quyết định, không làm F1 hoặc bearish recall tự tăng.

Score đã qua cân bằng lớp/temperature/EMA, chưa phải xác suất hiệu chỉnh, lợi suất kỳ vọng hay thước đo mức độ thiệt hại trong cú giảm. Frontend hiển thị score thập phân và ngày dữ liệu; không hiện score native thành phần trăm “độ tin cậy”. Trường `confidence=0` trong DTO cũ chỉ để giữ tương thích, không dùng cho phân bổ native; đọc `nativeForecast` và `scoreSemantics`.

## So sánh chính sách trên lịch sử

Report: `ml/reports/regime_net_taa/20261019T103518_043509Z/`.

Đây là proxy VNINDEX/cash: anchor stock35%, cash65%, cash return0, chi phí20bps trên notional giao dịch, có drift và tái cân bằng hàng ngày. Tín hiệu sau close t, thực hiện tại close t+1, nhận return t+1→t+2. Ngày thiếu dự báo về SAA. Không giả định được mua tại chính giá close đã dùng để tính tín hiệu.

| Fold | SAA: tổng return | Net score: tổng return | SAA: max drawdown | Net: max drawdown |
|---|---:|---:|---:|---:|
| 1 | 30,63% | 31,10% | −5,14% | −5,06% |
| 2 | −5,21% | −4,20% | −16,15% | −16,21% |
| 3 | 3,05% | 2,42% | −6,42% | −6,41% |
| 4 | 14,25% | 13,63% | −6,65% | −6,95% |

Net score có turnover thấp hơn winner-score proxy không gate, nhưng vẫn cao hơn SAA và không tốt hơn về return/drawdown ở mọi fold. Không tự bật TAA từ kết quả này. Winner proxy áp công thức cũ lên **cùng score của ensemble**, không phải backtest model ONNX cũ. Giá chỉ số không phải giá khớp lệnh tài sản mua được; proxy chưa mô phỏng gold/savings/cổ tức/thuế Việt Nam đầy đủ. Không có claim lợi nhuận hay test độc lập.

## Đã kiểm tra

- PostgreSQL thật trong schema test riêng:6tests về đồng thời, idempotency, revision conflict, out-of-order, rollback, gap reset và tách mode.
- Model thật + feature builder thật + PostgreSQL: preview khớp, restart trả đúng bản cũ không infer lại, freshness guard hoạt động.
- Java kiểm tra HTTP contract, score không hợp lệ, mode historical, lỗi worker, endpoint Spring và optimizer thực sự dùng native thay vì stock ONNX.
- Java gọi worker Python thật: snapshot cũ bị chặn, không tạo tín hiệu hiện tại.
- Kiểm tra proxy TAA có execution delay, cost và drift.
- Native serialization/score-state regression tests, frontend production build và smoke desktop/mobile ở trạng thái ready/unavailable.

DB thử nghiệm tách khỏi DB ứng dụng; không tự áp migration lên DB danh mục hiện có trong quá trình kiểm tra. Hướng dẫn khởi động ứng dụng ở trên là bước áp Flyway trong môi trường của người dùng.


## Chọn SAA/TAA và kỳ hạn dự báo (19/10/2026)

Trong tab **Tín hiệu thị trường**, dùng nút **Dùng SAA** / **Dùng TAA** và chọn
**T+20 / T+60 / T+120 phiên**. Lựa chọn lưu theo tài khoản trong
`allocation_preferences` (migration V10); mặc định SAA, 20 phiên. Chỉnh tỷ trọng
SAA chỉ thay mỏ neo, không tự bật TAA. Đổi chế độ/kỳ hạn chưa thực hiện giao dịch;
phải xem và xác nhận kế hoạch mới. Token xác nhận bao gồm cả chế độ và kỳ hạn.

TAA theo hướng lớp thắng (argmax của ba score): tăng +10 **điểm phần trăm**
cổ phiếu, giảm −10 điểm %, đi ngang hoặc dự báo không hợp lệ giữ SAA. Ví dụ
SAA 35% cổ phiếu → TAA giảm 25%. Giới hạn 0–100% và không vượt phần vốn còn
lại sau vàng; giữ tỷ trọng vàng SAA, chia phần còn lại cho tiết kiệm/tiền mặt
theo tỷ lệ SAA. Đây là quy tắc phân bổ được cấu hình, không phải dự báo mức sinh lời.
Cường độ net score không nhân vào bước 10 điểm % trong chế độ này.

T+20 vẫn dùng ensemble native đã có. T+60/T+120 là **baseline thử nghiệm riêng**
`experimental-close-etf-lgbm-v1-T60/T120`, chưa đánh giá OOS, không cùng mức
kiểm định với T+20. Không đổi nhãn dự báo T+20 thành kỳ hạn dài. Nhãn lợi suất
60 phiên dùng ngưỡng ±10%, 120 phiên ±15% theo `train_regime_v2.HORIZONS`.
Feature close/ETF được tính trên lịch phiên đầy đủ; chỉ dùng nhãn đã đáo hạn
đến phiên dự báo, không dùng nhãn tương lai. Class-balanced score chưa được
hiệu chỉnh thành xác suất. Receipt ghi cutoff nhãn, số mẫu, hash dữ liệu/code.

Worker nền huấn luyện baseline và công bố một kết quả mỗi kỳ hạn mỗi phiên
hoàn tất; lưu vào `ml_long_horizon_predictions`, khóa PostgreSQL chống chạy
trùng. Request API chỉ đọc kết quả đã công bố; restart cùng ngày đọc cache.
Chưa có kết quả hoặc cập nhật thất bại: hiển thị chưa có dự báo, giữ SAA.
Cần restart backend/worker để áp dụng V10 và worker mới; frontend tải lại.

API: `GET/PUT /api/v1/profile/allocation-preference`, body PUT
`{"mode":"TAA","horizonSessions":60}` (yêu cầu đăng nhập).
`POST /api/v1/research/native-regime/prediction?horizon=60` đọc dự báo đã cache.
Các lựa chọn hợp lệ là 20/60/120; không có chế độ mua bán tự động khi đổi lựa chọn.

## Chọn ETF hoặc cổ phiếu riêng lẻ

Chỉ tab Khảo sát có câu hỏi **Bạn muốn đầu tư phần cổ phiếu
bằng cách nào?** Lưu lựa chọn riêng theo tài khoản:

- ETF: toàn bộ tỷ trọng cổ phiếu dùng ETF VN30 `E1VFVN30`.
- Cổ phiếu riêng lẻ: phân bổ theo tỷ lệ các mã riêng lẻ đang nắm giữ, loại ETF
  ra khỏi nhóm này. Chưa có cổ phiếu thì phần vốn tương ứng chờ ở tiền mặt;
  người dùng chọn và mua mã tại tab Thị trường trước.
- Kết hợp: tỷ lệ ETF nằm trong phần cổ phiếu. Ví dụ cổ phiếu 40% NAV và tỷ lệ
  ETF 60% → ETF 24% NAV, cổ phiếu riêng lẻ 16% NAV.

Đây là lựa chọn công cụ, không đổi điểm khảo sát hoặc tổng tỷ trọng SAA/TAA.
ETF VN30 và chỉ số dự báo VNINDEX có thể biến động khác nhau. Không hỗ trợ hợp
đồng tương lai VN30F1 trong luồng này.

`GET/PUT /api/v1/profile/equity-preference`, yêu cầu đăng nhập, body ví dụ:
`{"mode":"MIXED","etfWeight":0.6}`. Chưa lưu lựa chọn thì giữ hành vi kế hoạch
cũ; không tự chuyển tài khoản hiện hữu sang ETF. Migration V11 lưu dữ liệu.
Lưu lựa chọn chỉ lập lại kế hoạch, không tự giao dịch. Token xác nhận bao gồm
cả lựa chọn này; đổi lựa chọn sẽ vô hiệu token cũ. Kế hoạch kiểm tra thêm độ
lệch từng công cụ (ngưỡng 5% NAV), có thể bán cổ phiếu để mua ETF ngay cả khi
đúng tổng tỷ trọng cổ phiếu. Lệnh theo lô 100, có phí/thuế và giữ dự trữ tiền
mặt; lô lẻ và sai lệch nhỏ có thể còn lại. Thiếu giá hợp lệ thì không đề xuất
mua mã đó. Người dùng phải xem và xác nhận kế hoạch trước khi thực hiện.
