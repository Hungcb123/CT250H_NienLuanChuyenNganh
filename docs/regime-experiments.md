# Thí nghiệm cải thiện regime: cố định phép so sánh

Công cụ: `ml/experiment_regime.py`. Đây là nghiên cứu development, chưa phải
kết quả holdout mới. Công cụ không export ONNX, không ghi model backend và không
thay đổi nhãn/ngưỡng hoặc dữ liệu gốc. Lần full đã xem vẫn được giữ nguyên.

## Việc đã chuẩn bị

- Báo cáo lỗi lần trước: `ml/reports/regime_diagnostics/20261017T135531_744801Z/`.
  `fold_errors.csv` có 48 dòng tương ứng 12 cấu hình × 4 fold, được suy ra trực
  tiếp từ confusion matrix đã có; không fit model để tạo báo cáo này.
- Preflight T+20 đạt 12 cấu hình: 4 nhóm feature × 3 cửa sổ train, cùng LightGBM.
- Các ngày validation khớp report `20261017T135531_744801Z`: mỗi fold 390 ngày,
  lần lượt 27/03/2020–14/10/2021, 15/10/2021–14/07/2023,
  17/07/2023–07/02/2025 và 10/02/2025–03/09/2026.
- Mỗi fold có 7 lần refit khi dùng lịch mặc định 63 phiên VNINDEX. Đây là 63
  phiên trên lịch chỉ số gốc, không phải 63 dòng còn lại sau khi ETF thiếu giá.

Chưa chạy train trên dữ liệu thị trường cho các cấu hình mới; chưa biết chúng
có cải thiện điểm hay không.

## Cách chạy tại thư mục gốc

Kiểm tra lại toàn bộ kế hoạch, không train:

```bash
python3 ml/experiment_regime.py --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json --audit-only
```

Chạy thử hai cấu hình (baseline và thêm cả trend/risk), cửa sổ expanding:

```bash
python3 ml/experiment_regime.py --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json --feature-groups baseline long --train-windows expanding --quick
```

So sánh đầy đủ 12 cấu hình T+20, mặc định LightGBM:

```bash
python3 ml/experiment_regime.py --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json
```

Mặc định 15 trials, timeout 60 giây cho mỗi lần tuning tại đầu outer fold;
`--quick` dùng 5 trials/30 giây. Mỗi cấu hình có 4 lần tuning, mỗi trial chạy
2 inner fold. Toàn bộ 12 cấu hình tương ứng 48 study và 336 lần refit định kỳ,
ngoài số lần fit trong tuning. Vì vậy không kỳ vọng full grid chỉ mất 1–2 phút.
Timeout không ngắt một trial đang chạy.

Muốn tách thí nghiệm thành từng nhóm để tiết kiệm thời gian:

```bash
# Chỉ kiểm tra feature, cùng cách train expanding
python3 ml/experiment_regime.py --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json --train-windows expanding

# Kiểm tra cửa sổ train với baseline, giữ feature cố định
python3 ml/experiment_regime.py --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json --feature-groups baseline
```

Có thể thêm `--models XGBoost`, `--trials`, `--timeout`, `--inner-splits` hoặc
`--refit-sessions`. T+20 là ưu tiên; T+60/T+120 được hỗ trợ qua `--horizons` nếu
report tham chiếu có fold tương ứng và tất cả train/inner fold qua preflight.
Thiếu mẫu/thiếu lớp thì dừng trước tuning, không lặng lẽ bỏ fold khó.

`--data-dir` mặc định trỏ tới snapshot `brokers_2010_20261001_reviewed` đã chuẩn
bị. Khi đổi data-dir, hash VNINDEX/ETF phải khớp audit của report tham chiếu.
Để nghiên cứu snapshot khác, cần thiết kế và ghi nhận một cohort tham chiếu
phù hợp; không đổi CSV ngầm rồi so điểm như cùng bài kiểm tra.

Windows PowerShell: dùng `python` thay `python3` nếu đang kích hoạt `.venv`.

## Bốn nhóm feature

Tất cả dựa trên cùng baseline `close-etf`: 12 feature VNINDEX + 4 feature ETF
đã có. Dùng `--base-feature-set close` chỉ khi report tham chiếu có cấu hình
`close` và muốn làm thí nghiệm riêng cho baseline không ETF.

| Nhóm | Feature thêm | Tổng số với close-etf |
|---|---|---:|
| `baseline` | Không thêm | 16 |
| `trend` | ROC60, ROC120, khoảng cách SMA200 | 19 |
| `risk` | Drawdown120, Drawdown252, HV20/HV60, downside volatility 60 | 20 |
| `long` | Cả trend và risk | 23 |

ROC và khoảng cách SMA/drawdown là phần trăm. Drawdown ở đây là giá hiện tại
chia đỉnh trong cửa sổ trừ một; không phải mức sụt giảm lớn nhất trên toàn đường
đi. HV dùng độ lệch chuẩn log-return, ddof=1. Downside volatility là căn trung
bình bình phương phần âm của log-return trên **toàn bộ 60 return**, nhân
sqrt(252) và 100; không chỉ tính riêng các ngày giảm.

Mọi cửa sổ chỉ kết thúc ở close(t). Không backfill hay tự điền feature thiếu;
HV20/HV60 không xác định khi mẫu số bằng 0. Nếu feature mới thiếu trên một ngày
validation tham chiếu, preflight dừng thay vì xóa ngày để cải thiện điểm.

Các ứng viên trong một lần chạy cũng dùng cùng tập ngày train đủ feature.
Do đó thêm feature không làm thay đổi nhãn hoặc lặng lẽ đổi mẫu số so sánh.

## Cách chia thời gian và refit

1. Cố định ngày validation ngoài (outer) từ report vừa chạy. Không dùng điểm
   cao/thấp để chọn lại ranh giới hoặc xóa giai đoạn khó.
2. Ở đầu mỗi outer fold, chỉ lấy mẫu có `label_end_date` nhỏ hơn ngày đầu fold.
3. Optuna chạy 2 inner fold purged trên đoạn đó. Tham số thắng được cố định
   cho toàn bộ outer fold, không chọn lại bằng nhãn của chính fold đó.
4. Mỗi 63 phiên thị trường, refit với các nhãn đã hoàn tất **trước** ngày bắt
   đầu block tiếp theo. Những nhãn từ block trước chỉ được dùng khi đã hoàn
   tất; đây là mô phỏng cập nhật theo thời gian, không phải nhìn trước.
5. Cửa sổ `3y`/`5y` giới hạn ngày feature trong 3/5 năm lịch tính từ đầu block.
   `expanding` dùng toàn bộ lịch sử đủ feature trước đó. Sau giới hạn vẫn purge
   theo ngày kết thúc nhãn và yêu cầu >=30 mẫu, đủ ba lớp.

Tuning chỉ diễn ra tại đầu outer fold, không tại mỗi lần refit 63 phiên.
Các hyperparameter chọn trong inner fold không nhìn thấy nhãn outer chưa biết.
Tuy nhiên, người nghiên cứu đã xem lịch sử này và đang chọn nhóm feature/cửa
sổ theo điểm outer, nên đây vẫn là **development comparison**, không phải một
holdout độc lập mới.

## Đọc kết quả

Mỗi lần chạy tạo thư mục riêng trong `ml/reports/regime_experiments/<timestamp>/`:

- `experiment_plan.json`: hash report/dữ liệu, feature, nhãn, ngày validation
  và hash danh sách ngày, lịch refit, preflight errors.
- `experiment_report.json`: tuning ở từng outer fold, điểm outer, ngày train
  và ngày nhãn cuối tại từng refit, confusion matrix và điểm theo năm quyết định.
- `comparison.csv` / `comparison.md`: trung bình F1, SD giữa fold, fold tệ nhất,
  MCC và số fold hơn majority baseline.
- `fold_errors.csv` và `year_errors.csv`: số báo giảm sai, bỏ lỡ giảm và tỷ lệ
  theo từng fold/năm. Một năm có thể chỉ có một phần validation, không mặc
  định đại diện cả năm thị trường.
- `paired_deltas.csv`: chênh lệch với cấu hình **baseline + expanding + cùng
  model/horizon trong chính lần chạy này**. Nếu không có control đó, không có
  phép so cặp; nên giữ baseline/expanding trong lần chạy dùng để kết luận.
- `*_predictions.csv`: ngày feature, ngày kết thúc nhãn, nhãn thật, return,
  dự đoán, baseline majority riêng từng lần refit và số hiệu fold/block.
- `model_comparison_t20.png`: F1 trung bình ± SD fold và majority baseline;
  bên dưới là precision/recall lớp giảm gộp qua các dự đoán.

TP: báo giảm và thực tế giảm. FP: báo giảm sai. FN: có giảm nhưng bỏ lỡ.
Precision = TP/(TP+FP), recall = TP/(TP+FN). False-alarm rate = FP/số mẫu thực
không giảm; nó khác false-discovery rate = FP/số lần báo giảm. Tỷ lệ không có
mẫu số được ghi null/ô trống, không ngụy trang thành 0% lỗi.

Ưu tiên một ứng viên cải thiện qua nhiều fold, MCC và fold tệ nhất tốt hơn,
đồng thời giảm bỏ lỡ mà không làm báo động sai tăng quá nhiều. Đừng chỉ chọn
cột F1 cao nhất. Không có cam kết các feature mới sẽ đạt những điều này.

**Không so trực tiếp điểm nested/refit mới với 0.385 của report cũ** để gán
công cho feature: cách tuning và refit cũng đã đổi. Phải dùng baseline được
chạy lại trong cùng phép thí nghiệm. SD fold là độ phân tán mô tả, không phải
khoảng tin cậy; nhãn horizon chồng lấn không phải các đợt giảm độc lập.

Chưa thêm ngưỡng confidence, hiệu chỉnh xác suất, nhãn theo volatility hoặc
backtest giao dịch. Những thay đổi đó là thí nghiệm riêng sau khi đánh giá
nhóm feature và cửa sổ train.

## Kiểm tra không train

```bash
python3 -m unittest discover -s ml -p 'test*regime*.py' -v
```

Estimator trong test thí nghiệm được mock. Test kiểm tra feature không đổi khi
thay giá tương lai, công thức cửa sổ, lịch refit qua gap, purge inner/outer,
cohort bất biến, hash nguồn, báo giảm sai/bỏ lỡ và báo cáo so cặp.
