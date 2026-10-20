# Model dự đoán xu hướng VNINDEX: trọng số, phương pháp train và metrics

Ngày lập báo cáo: **19/10/2026**. Số liệu được đối chiếu với bundle đã xuất, file dự đoán và báo cáo audit trong repository.

## 1. Hiện đã có bộ trọng số chưa?

**Có. Đã có bộ model đã train, lưu xuống đĩa và nạp lại để dự đoán từ đặc trưng thị trường.** Đây là một ensemble — nhiều model thành phần ghép thành một quy trình dự đoán — tên `shock_shrink_native_snapshot_v1`.

Vị trí:

```text
ml/artifacts/regime_shock_candidate_20261019T090555_259289Z/
├── contract.json             # Cấu hình, nguồn, ngày dữ liệu và trạng thái
├── checksums.json            # Hash kiểm tra các file lúc xuất
├── preview.json              # Kết quả xem thử snapshot, khởi động EMA mới
└── native/
    ├── trend.txt            # LightGBM classifier xu hướng/thông tin
    ├── risk.txt             # LightGBM classifier rủi ro
    ├── quantile_*.txt       # 90 LightGBM quantile regressors
    ├── forest_mean_*.joblib # 2 Random Forest theo lợi suất cuối kỳ
    ├── magnitude_*.joblib   # 2 Random Forest theo lợi suất và độ lớn
    ├── shock_*.joblib       # 4 Random Forest có đặc trưng shock
    ├── empirical.npz        # Lợi suất mẫu, leaf IDs, kho analog, median/IQR
    ├── bundle.json          # Schema đầu vào, danh sách model, môi trường
    └── bundle.sha256        # Hash metadata bundle
```

Tổng cộng **100 model được huấn luyện**: 2 classifier + 90 quantile regressor + 8 forest. Có **92 file LightGBM `.txt` và 8 file forest `.joblib`**. Một model chứa nhiều cây; 100 model không có nghĩa là chỉ có 100 cây.

Với mô hình cây, “trọng số” là cấu trúc cây, điều kiện chia nhánh và giá trị lá đã học, không phải một ma trận trọng số kiểu neural network. File LightGBM `.txt` là model thật, không phải báo cáo văn bản. Ngoài model, phải giữ `empirical.npz`: forest cần mẫu lợi suất trong các lá, analog cần kho trạng thái lịch sử và bộ chuẩn hóa. Chỉ sao chép các file cây sẽ chưa đủ để tái hiện thuật toán.

Đây là **bộ native Python/LightGBM/scikit-learn**. Code server đã được tích hợp qua worker Python và PostgreSQL; Java nhận score native, không cần đổi ensemble này thành một file ONNX. Cách khởi động, trạng thái TAA và giới hạn dữ liệu được ghi trong [REGIME_SERVER_VA_TAA.md](REGIME_SERVER_VA_TAA.md).

## 2. Model dự đoán điều gì và tạo nhãn như thế nào?

Đối tượng: **chỉ số VNINDEX**. Horizon: **20 phiên giao dịch tiếp theo**, không phải 20 ngày lịch hay dự báo từng cổ phiếu.

Tại phiên đóng cửa `t`, đặt:

```text
r[t]        = log(P[t] / P[t-1])
sigma_H[t]  = std(20 lợi suất log gần nhất, ddof=1) × sqrt(20)
R_future[t] = log(P[t+20] / P[t])
```

Nhãn đánh giá:

| Điều kiện | Lớp | Signal đầu ra |
|---|---|---:|
| `R_future < -sigma_H` | bearish — giảm | -1 |
| `-sigma_H <= R_future <= sigma_H` | sideway — trong vùng biến động | 0 |
| `R_future > sigma_H` | bullish — tăng | +1 |

Mã lớp nội bộ để train lần lượt là `0 / 1 / 2`; khi xuất signal sẽ trừ 1.

**Ngưỡng hiện tại là ±1 sigma, không phải cố định ±5%, cũng không phải trung bình lợi suất tăng trong quá khứ.** Sigma đo độ biến động. `sqrt(20)` là quy tắc chuẩn hóa đã chọn, không phải lời khẳng định thị trường luôn tuân theo giả định phương sai tăng tuyến tính theo thời gian.

Quy đổi sang lợi suất đơn: ngưỡng tăng là `exp(sigma_H)-1`, ngưỡng giảm là `exp(-sigma_H)-1`. Ví dụ tại snapshot **01/10/2026**, `sigma_H ≈ 0,0417673`: bullish khi lợi suất cuối 20 phiên lớn hơn khoảng **+4,27%**, bearish khi thấp hơn khoảng **−4,09%**. Hai ngưỡng thay đổi theo từng phiên. Sideway không có nghĩa giá đứng yên hoặc đường đi trong 20 phiên không có biến động mạnh.

## 3. Đầu vào và dữ liệu train

Nhóm đầu vào chính là chỉ báo từ VNINDEX, tương quan/lợi suất tương đối với ETF E1VFVN30, xu hướng dài hơn, biến động/drawdown và OHLCV. Trong nghiên cứu còn so sánh VIX và các chỉ số nhóm; cấu hình snapshot cuối chọn nhóm bổ sung **OHLCV** cho classifier trend.

| Thành phần snapshot | Số đặc trưng | Nội dung chính |
|---|---:|---|
| Trend classifier | 25 | 19 close/ETF/trend + 6 OHLCV |
| Risk classifier | 20 | 16 close/ETF + 4 risk |
| Quantile và forest thường | 19 | Close/ETF/trend |
| Shock forest | 35 | 19 đầu vào trên + 16 đặc trưng shock |
| Analog compact / full | 6 / 19 | Hai cách biểu diễn trạng thái thị trường |

Cả ensemble sử dụng **45 tên đặc trưng khác nhau**. Mỗi model chỉ nhận tập và thứ tự cột ghi trong `native/bundle.json`.

Các đặc trưng gồm RSI, MACD, Bollinger, khoảng cách đến SMA, ROC, historical volatility, drawdown, downside volatility, spread return ETF, các cú sốc lợi suất chuẩn hóa, tỷ lệ phiên giảm và mức tăng tốc momentum. OHLCV có các biến như biên độ trong phiên theo sigma, vị trí đóng cửa, thân/nến và volume tương đối.

Snapshot có mốc refit **01/10/2026**, được tạo ngày **19/10/2026**:

| Nhóm train | Số mẫu | Chính sách lịch sử | Ngày bắt đầu mẫu | Endpoint nhãn muộn nhất |
|---|---:|---|---|---|
| Trend classifier | 726 | Rolling 3 năm | 02/10/2023 | 30/09/2026 |
| Risk classifier | 726 | Rolling 3 năm | 02/10/2023 | 30/09/2026 |
| Density, forest, analog | 2.340 | Expanding các ngày đủ điều kiện | 25/02/2016 | 30/09/2026 |

Ngày mẫu là ngày phát sinh đặc trưng; endpoint là ngày kết thúc 20 phiên tương lai của mẫu đó. Hai ngày này khác nhau. Các phiên cuối chưa biết đủ kết quả T+20 vẫn giữ để **suy luận**, không được đưa vào train như nhãn đã biết.

Không điền ngược giá trước khi dữ liệu tồn tại. ETF thiếu dữ liệu không được tạo giá giả. OHLCV xung đột nguồn giữ missing theo quy tắc consensus; LightGBM xử lý missing ở các đầu vào cho phép. Analog yêu cầu các đặc trưng của view phải hữu hạn. Đồng thuận giữa nguồn chưa chứng minh hoàn toàn chất lượng dữ liệu hoặc thời điểm công bố lịch sử.

## 4. Phương pháp huấn luyện từng thành phần

### 4.1. Hai LightGBM classifier

Hai model học trực tiếp ba lớp bearish/sideway/bullish bằng multiclass classification. Cả hai dùng `class_weight=balanced`, tăng trọng số tương đối của lớp ít mẫu. Điểm classifier chung là trung bình bằng nhau của hai đầu ra.

Hyperparameter xuất phát từ Optuna trên các fold **quá khứ có purge**, trong nghiên cứu fixed ±5% trước đó, rồi được **tái sử dụng và train lại với nhãn ±1 sigma**. Không phải toàn bộ tham số đã được tối ưu riêng cho nhãn động. Đợt Optuna nguồn khai báo 15 trials, timeout 60 giây, 2 inner splits; không nên suy ra tất cả lần chạy đều hoàn thành đủ 15 trials nếu chưa kiểm tra từng trial log.

Các thông số chính của snapshot cuối:

| Thông số | Trend | Risk |
|---|---:|---:|
| `n_estimators` — số boosting rounds | 350 | 250 |
| `learning_rate` | 0,042721 | 0,121397 |
| `max_depth` | 5 | 3 |
| `num_leaves` — giới hạn số lá | 59 | 20 |
| `min_child_samples` | 42 | 23 |
| `colsample_bytree` | 0,819323 | 0,755471 |
| `class_weight` | balanced | balanced |
| `random_state` | 42 | 42 |

Model cây của LightGBM không có kernel linear/RBF như SVM. Các tham số thay đổi độ phức tạp, cách chia cây, learning rate và regularization.

### 4.2. Chín mươi LightGBM quantile regressors

Nhóm này học **phân vị của lợi suất tương lai**, thay vì chỉ học một nhãn cứng. Mục tiêu có hai dạng: lợi suất log T+20, và lợi suất log T+20 chia cho sigma biết tại ngày gốc.

```text
5 seed: 7, 21, 42, 84, 126
× 2 dạng mục tiêu: raw / normalized
× 9 phân vị: 0.05, 0.15, 0.25, 0.35, 0.50, 0.65, 0.75, 0.85, 0.95
= 90 model
```

Mỗi model tối ưu quantile/pinball loss. Cấu hình chính cố định: 300 boosting rounds, learning rate 0,03, max depth 4, tối đa 15 lá, min child samples 50, colsample 0,7, L1 0,1 và L2 1,0. Năm seed được lấy trung bình, không chọn seed tốt nhất theo điểm outer.

Khi suy luận: đổi kết quả normalized về lợi suất log, sắp xếp các phân vị để xử lý crossing, rồi cộng các trọng số atom cố định vào ba vùng dưới/trong/trên ±sigma. Sau đó chia cho tần suất lớp trong tập train đã trưởng thành và chuẩn hóa lại. Đây là **score cân bằng lớp từ phân phối xấp xỉ**, chưa phải xác suất đã hiệu chỉnh.

### 4.3. Tám Random Forest và phân phối lợi suất trong lá

| Nhóm | Số model | Mục tiêu dùng để học cách chia cây |
|---|---:|---|
| Forest thường | 2 | Lợi suất cuối kỳ, dạng raw và normalized |
| Magnitude forest | 2 | Lợi suất và trị tuyệt đối của nó, raw/normalized |
| Shock forest | 4 | Hai kiểu mục tiêu trên, raw/normalized, thêm 16 đặc trưng shock |

Với mục tiêu hai chiều, từng chiều được chuẩn hóa bằng mean/std **chỉ trên tập train**. Cấu hình mỗi forest: 300 cây, max depth 6, min samples leaf 30, max features 0,7, random state 42.

Kết quả dự đoán không đơn thuần là giá trị trung bình do regressor trả ra. Với mỗi phiên cần dự đoán, model tìm lá tương ứng ở từng cây, lấy các mẫu lợi suất train đã trưởng thành trong lá để đếm tỷ lệ thuộc ba lớp, rồi trung bình qua các cây. Phân phối trong lá dùng tất cả quan sát train rơi vào lá; bootstrap ảnh hưởng cấu trúc cây, không nhân bản các return atom theo số lần bootstrap. Score được cân bằng bằng prior lớp train.

### 4.4. Analog — các phiên lịch sử có trạng thái gần nhau

Analog không học một neural network hay booster riêng. Nó lưu kho trạng thái lịch sử và làm các bước:

1. Tính median/IQR của đặc trưng trên tập train; IQR bằng 0 được thay scale bằng 1.
2. Chuẩn hóa phiên cần dự đoán bằng các thống kê train đó.
3. Tìm 100 phiên gần nhất theo khoảng cách Euclidean; xử lý hòa khoảng cách theo thứ tự train cố định.
4. Gán trọng số Gaussian, bandwidth là median khoảng cách của các hàng xóm đã chọn. Nếu bandwidth bằng 0, chỉ dùng các hàng xóm có khoảng cách 0 đã chọn.
5. Dùng lợi suất T+20 đã biết của các phiên tương tự để ước lượng ba vùng nhãn, rồi cân bằng theo prior train.

Lấy trung bình bốn cách: compact/raw, compact/normalized, full/raw và full/normalized. Mọi return atom phải có endpoint trước mốc refit.

## 5. Ghép các thành phần thành một dự đoán

Ký hiệu `C` là trung bình hai classifier; `Q` là nhóm quantile; `R` là forest thường; `M` là magnitude forest; `A` là analog; `S` là shock forest. Mỗi đại lượng là một vector ba score.

```text
B = 0.50 Q + 0.25 R + 0.25 M
L = 0.75 B + 0.25 A
D = 0.75 L + 0.25 S
```

Tương đương bên trong density `D`: Q 28,125%; R 14,0625%; M 14,0625%; A 18,75%; S 25%.

Với snapshot cuối, bộ ba tham số `0.75 0.75 1.5` nghĩa là:

```text
w  = 0.75      # Tỷ trọng density sau bước temperature
Tc = 0.75      # Temperature của classifier
Td = 1.50      # Temperature của density

C_temp = normalize(C ** (1 / Tc))
D_temp = normalize(D ** (1 / Td))
raw    = (1 - w) C_temp + w D_temp
EMA[t] = (1/3) raw[t] + (2/3) EMA[t-1]   # EMA span 5
final  = 0.5 raw + 0.5 EMA
signal = argmax(final) - 1
```

Các tỷ trọng bên trong density không phải đóng góp tuyến tính cuối cùng của từng model, vì còn bước temperature và EMA. Temperature ở đây là tham số kết hợp, không chứng nhận xác suất đã được hiệu chỉnh.

Trong đánh giá lịch sử, tham số fusion được chọn từ các inner fold có purge, rồi giữ tại outer fold tương ứng:

| Fold | w | Tc | Td |
|---|---:|---:|---:|
| 1 | 0,75 | 0,75 | 1,00 |
| 2 | 0,60 | 0,75 | 0,75 |
| 3 | 0,75 | 0,75 | 1,00 |
| 4 | 0,75 | 0,75 | 1,50 |

Snapshot cuối dùng cấu hình fold 4. Nhóm thông tin bổ sung cho trend cũng được chọn bằng inner evaluation; các fold lần lượt chọn VIX, indices, control và OHLCV.

EMA tiếp tục qua cuối tuần nếu hai ngày là hai phiên liên tiếp. Nếu thiếu dự báo của một phiên giao dịch thì reset. Chạy CLI lần đầu không có state sẽ cold start, vì vậy không được đồng nhất kết quả một lần chạy đó với chuỗi lịch sử đã có EMA liên tục.

## 6. Cách đánh giá và chống nhìn trước tương lai

Sử dụng **walk-forward theo thời gian**, không random shuffle. Tổng cộng 1.560 ngày đánh giá, chia 4 outer folds, mỗi fold 390 ngày. Huấn luyện lại sau các block 63 phiên theo lịch thị trường gốc: tổng cộng 28 lần refit.

Một mẫu train chỉ được dùng nếu `label_end_date < prediction_block_start`. Có purge các mẫu có nhãn chưa trưởng thành ở biên. Nhãn và endpoint được tạo trên lịch VNINDEX đầy đủ trước khi lọc feature; không đếm T+20 trên chuỗi đã loại ngày thiếu dữ liệu.

Trend/risk classifier dùng rolling 3 năm. Quantile, forest và analog dùng expanding các mẫu đủ điều kiện. Scale/standardization/prior của mỗi lần fit chỉ lấy từ train. Smoothing chỉ dùng score hiện tại và quá khứ, không dùng nhãn tương lai.

Đã xuất/nạp lại 28 bộ native từ các mốc lịch sử và đối chiếu với nghiên cứu: **1.560/1.560 nhãn dự đoán khớp**, sai số score lớn nhất khoảng **3,33 × 10⁻¹⁶**. Audit độc lập kiểm tra 2.828 payload native và 84 receipt cohort huấn luyện. Năm test mới kiểm tra code/serialization/maturity/state/path targets đã đạt.

**Các kiểm tra này xác nhận tính nhất quán của triển khai, không chứng minh khả năng dự đoán tương lai.** Lịch sử outer đã được xem qua nhiều lần nghiên cứu; chưa có tập final test độc lập. Các nhãn T+20 còn chồng lấn, nên 1.560 ngày không phải 1.560 mẫu độc lập hoàn toàn. Dùng ETF tránh việc áp trực tiếp rổ cổ phiếu hiện tại về quá khứ, nhưng không tự chứng minh mọi nguồn dữ liệu đều có vintage point-in-time được chứng nhận.

## 7. Metrics là gì và model đạt bao nhiêu?

### 7.1. Ý nghĩa metrics

Với một lớp, coi lớp đó là positive và hai lớp còn lại là negative:

| Metric | Công thức / ý nghĩa |
|---|---|
| Precision | `TP / (TP + FP)`: trong các lần báo lớp đó, bao nhiêu lần đúng? |
| Recall | `TP / (TP + FN)`: trong các lần lớp đó thực sự xảy ra, bắt được bao nhiêu? |
| F1 mỗi lớp | `2 × Precision × Recall / (Precision + Recall)`; bằng `2TP / (2TP+FP+FN)` |
| Macro F1 | Trung bình đều F1 của bearish, sideway, bullish; không để lớp đông mẫu quyết định toàn bộ điểm |
| Mean fold macro F1 | Tính macro F1 riêng từng fold, rồi lấy trung bình 4 fold; **metric chính để so model** |
| Worst fold F1 | Macro F1 thấp nhất trong 4 fold; thể hiện giai đoạn yếu nhất đã quan sát |
| Accuracy | Số dự đoán đúng / tổng số dự đoán |
| MCC đa lớp | Mức liên hệ giữa nhãn thật và dự đoán có xét toàn bộ confusion matrix; trong [-1,1], gần 1 tốt, 0 là không có liên hệ theo thước đo này |
| Brier score | Trung bình tổng bình phương sai lệch giữa vector dự báo và vector nhãn one-hot; thấp tốt hơn |
| Log loss | Phạt khi gán ít xác suất cho lớp thực sự xảy ra; thấp tốt hơn |

F1 không phải accuracy, xác suất đúng của từng phiên hay tỷ suất lợi nhuận. “Dự đoán ngẫu nhiên thì macro F1 luôn 33,3%” cũng không đúng chung: còn phụ thuộc phân bố lớp và cách dự đoán.

### 7.2. Kết quả chính của shock_shrink đã xuất native

| Metric | Kết quả | Cách tổng hợp |
|---|---:|---|
| **Mean fold macro F1** | **51,3745%** | Trung bình 4 macro F1 |
| Worst fold macro F1 | 40,3056% | Fold thấp nhất |
| Mean fold MCC | 0,3005 | Trung bình 4 MCC |
| Accuracy | 63,7179% | 994/1.560 dự đoán đúng |
| Macro F1 gộp | 52,9824% | Gộp confusion matrix của cả 1.560 ngày |
| MCC gộp | 0,3115 | Tính trên cả 1.560 ngày |

**51,37% và 52,98% không mâu thuẫn**: một số lấy trung bình F1 từng fold, một số tính F1 sau khi gộp toàn bộ mẫu. Metric báo cáo chính vẫn là **51,37%**, không chuyển sang số cao hơn để quảng bá kết quả.

Nếu luôn dự đoán sideway trên chính tập này, accuracy là 954/1.560 = **61,15%**. Vì vậy không thể chỉ nhìn accuracy 63,72% rồi kết luận model rất mạnh. Macro F1 và kết quả từng lớp cung cấp thêm thông tin.

### 7.3. Kết quả từng giai đoạn

| Fold | Thời gian phát sinh dự báo | Số phiên | Macro F1 | Accuracy | MCC |
|---|---|---:|---:|---:|---:|
| 1 | 27/03/2020–14/10/2021 | 390 | 56,4261% | 65,1282% | 0,3706 |
| 2 | 15/10/2021–14/07/2023 | 390 | 65,4374% | 71,7949% | 0,5131 |
| 3 | 17/07/2023–07/02/2025 | 390 | 40,3056% | 57,4359% | 0,1110 |
| 4 | 10/02/2025–03/09/2026 | 390 | 43,3289% | 60,5128% | 0,2073 |

Endpoint T+20 cuối của tập đánh giá là 01/10/2026. Ngày phát sinh dự báo cuối là 03/09, không phải ngày endpoint đó.

### 7.4. Khả năng nhận diện từng lớp

**Bảng dưới gộp toàn bộ 1.560 phiên**, không phải trung bình chỉ số từng fold:

| Lớp | Số mẫu thật | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Bearish | 208 | 45,53% | 26,92% | 33,84% |
| Sideway | 954 | 72,53% | 76,10% | 74,27% |
| Bullish | 398 | 48,62% | 53,27% | 50,84% |

Nếu lấy **trung bình F1 từng lớp qua 4 fold**, các số tương ứng là bearish **31,42%**, sideway **74,36%**, bullish **48,35%**. Trung bình ba số này bằng macro F1 chính 51,37%.

Confusion matrix gộp, hàng là nhãn thật, cột là dự đoán:

| Thật / Dự đoán | Bearish | Sideway | Bullish |
|---|---:|---:|---:|
| Bearish | 56 | 108 | 44 |
| Sideway | 48 | 726 | 180 |
| Bullish | 19 | 167 | 212 |

Ví dụ thực tế: có 208 phiên mang nhãn bearish nhưng chỉ bắt được 56, bỏ lỡ 152. Tổng số lần báo bearish là 123, trong đó 67 lần sai. Nhận diện giảm còn yếu; khả năng tốt nhất hiện tại là lớp sideway. Biến động kết quả giữa các fold cũng còn lớn.

### 7.5. So sánh ứng viên và baseline cùng bài toán

| Phương án | Mean fold macro F1 | Worst fold F1 |
|---|---:|---:|
| Mốc đầu đợt cải thiện | 49,2508% | 40,0013% |
| Analog_shrink — cao nhất đã quan sát | **51,4488%** | 39,3661% |
| Shock_shrink — đã xuất native | **51,3745%** | **40,3056%** |
| Momentum 20 phiên so với sigma hiện tại | 37,6059% | 30,1554% |
| Giữ lớp của chu kỳ 20 phiên vừa hoàn tất | 37,9343% | 30,0335% |

Shock_shrink thấp hơn analog_shrink khoảng **0,0743 điểm phần trăm** về mean F1, nhưng worst fold cao hơn khoảng **0,9395 điểm phần trăm**, và mean MCC 0,3005 cao hơn 0,2978. Đây là lý do ưu tiên xuất bản shock để chuẩn bị triển khai; chưa chứng minh nó sẽ tốt hơn trên dữ liệu tương lai.

Các thử nghiệm mới về close-only analog với lịch sử dài hơn và forest có thêm supervision đường giá chưa vượt mốc cao nhất, nên không thay ứng viên. Các kết quả trên thuộc **cùng nhãn động**; không dùng chúng để so trực tiếp với F1 của bài toán fixed ±5% cũ.

### 7.6. Kiểm tra score như xác suất

Đã thử một logistic calibrator nhân quả cố định: tối đa 504 score quá khứ có nhãn trưởng thành, ít nhất 120 mẫu và 10 mẫu/lớp, refit mỗi 20 phiên. So sánh trên **cùng 1.340 ngày có calibrator**:

| Đầu ra | Brier | Log loss |
|---|---:|---:|
| Score shock gốc | 0,52765 | 0,90394 |
| Tần suất 504 nhãn thị trường đã trưởng thành | 0,55972 | 0,96955 |
| Logistic calibration | 0,53369 | 0,93788 |

Logistic không cải thiện tổng thể so với score gốc. Riêng fold 3, cả hai còn thua baseline tần suất lớp về Brier. Point policy được giữ nguyên. Vì vậy `calibrated_probability` vẫn là `null`; không hiển thị một score như 0,509 thành “50,9% chắc chắn đi ngang”.

## 8. Metrics trên thuộc quy trình nào?

Các metrics 51,37% F1 và 63,72% accuracy thuộc **quy trình walk-forward gồm 28 lần train**, mỗi lần chỉ học từ quá khứ đã trưởng thành. Chúng không phải điểm train trên toàn dữ liệu, và cũng không phải điểm test riêng của bộ trọng số snapshot ngày 01/10.

Snapshot cuối đã được fit để có bộ model cụ thể có thể nạp và dự đoán. Tuy nhiên, nó được tạo ngày 19/10 từ dữ liệu đến 01/10. Preview không phải dự báo đã ghi từ 01/10 trước khi tương lai diễn ra. Chưa có số liệu prospective riêng đủ để báo cáo cho snapshot này; chưa có backtest giao dịch gồm chi phí để chứng minh lợi nhuận.

## 9. Cách chạy và các file nguồn để kiểm tra

Chạy snapshot đã có, không train lại:

```bash
python3 ml/predict_regime_shock.py \
  --bundle ml/artifacts/regime_shock_candidate_20261019T090555_259289Z/native \
  --parameters 0.75 0.75 1.5
```

Thêm `--require-fresh` để từ chối dữ liệu cũ quá 4 ngày lịch. Với snapshot này tại ngày lập báo cáo, lệnh phải từ chối vì dữ liệu cũ 18 ngày. Kiểm tra tuổi dữ liệu chưa thay thế việc xác minh lịch nghỉ sàn, độ trễ nguồn và thời điểm hoàn tất phiên.

Có thể dùng `--state-file /path/to/state.json` để lưu/nạp EMA giữa các lần chạy. Đây là CLI nghiên cứu cục bộ; chưa phải dịch vụ đa người dùng có khóa đồng thời và ledger dự báo bất biến. Bộ native có Python joblib, chỉ nạp các bundle cục bộ tin cậy.

Nếu cần tự train và xuất **snapshot mới từ cùng dữ liệu reviewed hiện có**:

```bash
python3 ml/build_regime_shock_candidate.py
```

Lệnh tạo thư mục artifact mới, không tự tải dữ liệu mới hay triển khai web. Muốn replay và xuất toàn bộ các mốc lịch sử, dùng `python3 ml/export_regime_shock_native.py`; đây là công việc nặng hơn chạy suy luận.

Các file liên quan, đường dẫn tính từ gốc repository:

| Mục đích | File |
|---|---|
| Metadata bộ model đã có | `ml/artifacts/regime_shock_candidate_20261019T090555_259289Z/native/bundle.json` |
| Train/xuất snapshot | `ml/build_regime_shock_candidate.py` |
| Train/xuất/replay 28 bộ lịch sử | `ml/export_regime_shock_native.py` |
| Nạp model và suy luận từng thành phần | `ml/regime_shock_native.py` |
| Tạo đầu vào, giữ cả phiên chưa có nhãn | `ml/regime_shock_features.py` |
| Ghép score, quản lý trạng thái EMA | `ml/regime_shock_score_runtime.py` |
| CLI suy luận | `ml/predict_regime_shock.py` |
| Metrics chi tiết và confusion matrix | `ml/reports/regime_shock_forest/20261019T072038_455776Z/report.json` |
| Kết quả native replay | `ml/reports/regime_shock_native/20261019T090304_754869Z/summary.json` |
| Audit độc lập, baseline và metrics tính lại | `ml/reports/regime_research/f1_goal_20261019_stage7/independent_audit.json` |
| Báo cáo chẩn đoán xác suất | `ml/reports/regime_shock_probabilities/20261019T090829_984153Z/report.json` |

**Trạng thái hiện tại:** đã có bộ trọng số và dữ liệu phụ trợ thực sự, đã kiểm tra suy luận khớp nghiên cứu và nối code server/giao diện qua worker native. TAA vẫn tắt mặc định; dữ liệu cũ sẽ trả không khả dụng và giữ SAA. Chưa chấp nhận score làm xác suất tin cậy, chưa có kiểm chứng tương lai độc lập. Cần khởi động các tiến trình, cập nhật dữ liệu và vận hành quy trình refit/ghi dự báo trước khi tuyên bố sẵn sàng dùng cho quyết định danh mục.
