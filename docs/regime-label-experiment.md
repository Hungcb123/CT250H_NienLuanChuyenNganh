# Thí nghiệm nhãn T+20: ±5% và chuẩn hóa volatility

Script riêng: `ml/experiment_regime_labels.py`. Không thay nhãn trong pipeline
cũ, không tìm model/kernel mới, không chấm holdout đã xem và không export ONNX.

## Cố định trước khi chạy

- Model: LightGBM, cùng không gian Optuna hiện có và `class_weight='balanced'`.
- Feature: `close-etf + trend`, tổng 19 feature.
- Cửa sổ train: 3 năm lịch; refit mỗi 63 phiên VNINDEX.
- Tuning: purged inner CV 2 fold, chọn riêng tham số cho từng bài toán nhãn.
- Ngày validation: bốn fold của report `20261017T135531_744801Z`, 390 mẫu/fold.
- Hai ứng viên nhãn được định nghĩa trước: `fixed_5pct` và `vol_1sigma`.
  Không tuning hệ số k, không qcut để ép ba lớp chia đều.

## Hai định nghĩa nhãn

`fixed_5pct` giữ nguyên return đơn giản:

```text
R(t,20) = P(t+20)/P(t) - 1
+1 nếu R > 0.05; -1 nếu R < -0.05; còn lại 0.
```

`vol_1sigma` chuẩn hóa log-return cuối kỳ:

```text
s(t) = std(log-return ngày trong 20 phiên kết thúc tại t), ddof=1
z(t,20) = log(P(t+20)/P(t)) / (s(t) * sqrt(20))
+1 nếu z > 1; -1 nếu z < -1; còn lại 0.
```

Code dùng encoding nội bộ 0/1/2 tương ứng bearish/sideway/bullish, tức nhãn
ngữ nghĩa -1/0/+1. Dấu bằng thuộc sideway. k=1, lookback=20 và horizon=20
được cố định trước, không chọn lại bằng điểm outer validation.

s(t) là độ lệch chuẩn **return ngày ở đơn vị thập phân**, không annualize và
không nhân 100. Nếu lấy từ `HV20` cũ, phải chia 100 và sqrt(252) để trở về đơn
vị đó. sqrt(20) là quy ước chuẩn hóa horizon; không đảm bảo phương sai tương lai
thực sự luôn tăng tuyến tính theo số phiên.

Ngưỡng simple return tương đương của nhãn volatility là:

```text
upper(t) = exp(s(t)*sqrt(20)) - 1
lower(t) = exp(-s(t)*sqrt(20)) - 1
```

Hai ngưỡng này không đối xứng hoàn toàn theo simple return. Đây là nhãn dựa
vào **điểm cuối kỳ**, không phải triple-barrier dựa vào rào chạm trước trên đường giá.

Volatility chỉ dùng giá đến t. Return/nhãn dùng giá t+20 để xác định kết quả,
nhưng chỉ được đưa vào train khi `label_end_date` đã ở trước thời điểm dự báo.
Nhãn được tính trên lịch VNINDEX gốc trước khi lọc feature/ETF. Sigma bằng 0,
thiếu hoặc nhãn chưa hoàn tất vẫn là missing; không tự điền. Nếu missing rơi
vào cohort đã cố định, preflight dừng thay vì xóa mẫu để đổi bài kiểm tra.

## Audit với dữ liệu hiện có

Cả hai ứng viên qua preflight, cùng 2.341 mẫu feature đủ lịch sử. Phân bố trên
**toàn cohort, gồm phần lịch sử train**, không phải riêng validation:

| Nhãn | Giảm | Đi ngang | Tăng |
|---|---:|---:|---:|
| fixed_5pct | 295 | 1.524 | 522 |
| vol_1sigma | 342 | 1.390 | 609 |

Trên riêng bốn fold validation, nhãn giảm lần lượt có 191 và 208 mẫu. Khi đọc
precision/recall phải phân biệt hai tập ground truth này; không so trực tiếp
số bắt đúng của hai bài toán như thể cùng mẫu giảm.

Trên toàn cohort, median ngưỡng volatility quy đổi về simple return là khoảng
**−3,90% / +4,06%**; percentile 10–90 của ngưỡng trên khoảng 2,39–8,52%.
Đây chỉ là thống kê mô tả của k=1 đã chọn trước, không phải kết quả tối ưu ngưỡng.
Không có bảo đảm lớp cân bằng hoặc điểm F1 tăng.

## Chạy từ thư mục gốc repo

Audit lại, không train:

```bash
python3 ml/experiment_regime_labels.py --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json --audit-only
```

Chạy thử cả hai nhãn với 5 trials/30 giây cho mỗi outer-fold tuning:

```bash
python3 ml/experiment_regime_labels.py --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json --quick
```

Chạy đầy đủ mặc định 15 trials/60 giây:

```bash
python3 ml/experiment_regime_labels.py --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json
```

Có thể chỉ định `--trials`, `--timeout`, `--data-dir`, `--output-dir`,
`--inner-splits` và `--refit-sessions`. Không có cờ thay model, nhóm feature,
cửa sổ train hoặc k trong thí nghiệm này. Thư mục output phải chưa tồn tại.
Hash dữ liệu phải khớp audit của report tham chiếu. Như Optuna hiện tại,
timeout không ngắt trial đang chạy nên có thể vượt số giây đã đặt.

Windows PowerShell: thay `python3` bằng `python` nếu môi trường dùng lệnh đó.

## Kết quả và cách đọc

Mỗi lần chạy tạo thư mục riêng `ml/reports/regime_labels/<UTC timestamp>/`:

- `label_plan.json`: công thức, đơn vị, hash dữ liệu/ngày, số lớp từng fold,
  quy tắc đánh giá và lỗi preflight nếu có.
- `label_definitions.csv`: cả hai nhãn, ngày kết thúc, sigma ngày/horizon,
  return thực tế, z và hai ngưỡng simple return cho từng mẫu cohort.
- `label_report.json`: kết quả development đầy đủ cho từng bài toán; không có
  trường chọn winner xuyên hai định nghĩa nhãn.
- `fixed_5pct_predictions.csv`, `vol_1sigma_predictions.csv`: dự đoán, nhãn của
  bài toán đang học, cả hai nhãn đối chiếu và metadata volatility.
- `native_metrics.csv`: F1/MCC/majority baseline trên **ground truth riêng của
  từng nhãn**. So model với majority của chính bài toán đó; không xếp hạng hai
  bài toán chỉ vì F1 của bên nào cao hơn.
- `common_5pct_risk.csv`: thước đo chung, ground truth luôn là return thực tế
  giảm **quá 5% sau 20 phiên**. Cùng mẫu và cùng định nghĩa lỗi cho cả hai bên.
- `fold_metrics.csv`: điểm nhãn riêng và lỗi theo thước đo chung ở mỗi fold.
- `conditional_forward_returns.csv`: số mẫu, mean/median return thực tế, tỷ lệ
  giảm quá 5%/tăng quá 5% trong từng nhóm dự đoán. Đây không phải lợi nhuận chiến lược.
- `comparison.md`: bảng nhãn riêng và bảng rủi ro chung, có giải thích giới hạn.

Ở thước đo chung: một dự đoán bearish từ model volatility được xem như một
cảnh báo cho mục tiêu giảm quá 5%. Nếu thực tế chỉ giảm 2%, đó có thể là nhãn
giảm đúng của bài toán volatility nhưng vẫn là báo động sai đối với mục tiêu
−5%. Hai cách nhìn này phải được báo cáo tách biệt.

Để kết luận có ích cho mục tiêu ban đầu, xem khả năng bắt giảm quá 5% có tốt
hơn mà không tăng báo động sai quá nhiều hay không, rồi xem độ ổn định từng
fold. F1 nhãn mới tăng nhưng rủi ro theo thước đo chung kém hơn không chứng minh
cải thiện mục tiêu ban đầu.

Các return 20 phiên chồng lấn không phải các giao dịch/đợt giảm độc lập.
Không có fee, execution, drawdown của danh mục hoặc test mới chưa xem. Cả hai
ứng viên vẫn là nghiên cứu development trên lịch sử đã được quan sát.

## Kiểm tra không train model

```bash
python3 -m unittest discover -s ml -p 'test*regime*.py' -v
```

Test mới kiểm tra đơn vị HV20, sqrt(horizon), ngưỡng không đổi khi sửa giá tương
lai, giữ horizon qua gap feature, sigma 0, nhãn chưa hoàn tất, cohort giống nhau,
purge từng policy, tách báo cáo và cùng ground truth −5%. Estimator được mock
ở test điều phối; không train trên dữ liệu thị trường.
