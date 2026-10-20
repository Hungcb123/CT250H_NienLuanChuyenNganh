# Regime v2: dữ liệu nghiên cứu và đánh giá theo thời gian

Chạy tại thư mục gốc repo. Pipeline mặc định dùng feature VNINDEX; không dựng
breadth lịch sử từ 30 mã hiện tại. Feature close(t) chỉ có sau khi phiên t đóng cửa.

## Lần chạy tiếp theo sau kết quả ngày 17/10/2026

Bộ dữ liệu đã chuẩn bị riêng tại `ml/data/research/brokers_2010_20261001_reviewed/`.
Không thay `ml/data/raw` hay kết quả/model đã chạy. VNINDEX có 4.174 phiên từ
04/01/2010 đến 01/10/2026. ETF có 2.675 dòng từ 07/01/2016, gồm một số dòng
volume 0 sẽ tiếp tục bị xem là giá chưa quan sát, không được điền.

Audit cả baseline và bản ETF, không train:

```bash
python3 ml/train_regime_v2.py --data-dir ml/data/research/brokers_2010_20261001_reviewed --development-only --audit-only --feature-sets close close-etf
```

Chạy thử gọn cho T+20, hai model và hai bộ feature:

```bash
python3 ml/train_regime_v2.py --data-dir ml/data/research/brokers_2010_20261001_reviewed --development-only --quick --feature-sets close close-etf --horizons 20 --models LightGBM XGBoost
```

So sánh cả ba horizon, LightGBM và XGBoost với 30 trials/cấu hình:

```bash
python3 ml/train_regime_v2.py --data-dir ml/data/research/brokers_2010_20261001_reviewed --development-only --feature-sets close close-etf --models LightGBM XGBoost --trials 30 --timeout 120
```

Muốn đủ 5 model, 60 trials và 300 giây/cấu hình, bỏ `--models`, `--trials` và
`--timeout` ở lệnh trên. Timeout Optuna kiểm tra giữa các trial, không ngắt trial
đang chạy nên tổng thời gian có thể vượt mức timeout.

Để dùng hết lịch sử từ 2010 cho riêng baseline, bỏ `--feature-sets close close-etf`
(mặc định là `close`). Khi so sánh hai bộ cùng một lần, pipeline dùng giao các
ngày hợp lệ để so sánh công bằng; dữ liệu so sánh bắt đầu từ 2016, không phải 2010.

**`--development-only` không chấm holdout, không export và không công bố điểm
test độc lập.** Nó dùng tất cả mẫu có nhãn đã hoàn tất để làm development CV.
`--quick` chỉ giảm còn 5 trials/30 giây, đồng thời cũng không chấm holdout/export.

Lần chạy full trước đã được xem, bao gồm nhãn kết thúc đến 01/10/2026. Không đổi
ranh giới sang một giai đoạn cũ rồi gọi đó là test mới. Script đọc
`ml/holdout_exposure.json` và các report cũ để chặn tái sử dụng nhãn đã xem.
Khi có giai đoạn mới thực sự chưa xem và đủ H phiên để hoàn tất nhãn, mới chạy
chế độ final với `--holdout-start YYYY-MM-DD` sau mốc đã ghi nhận. Không xóa sổ
exposure hay report để làm mới holdout.

## Cài môi trường

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r ml/requirements.txt
```

Windows PowerShell: dùng `py -m venv .venv`, kích hoạt bằng
`.\.venv\Scripts\Activate.ps1`, rồi thay `python3` bằng `python` trong các lệnh.

## Nguồn dữ liệu và cách tái tạo snapshot

```bash
python3 ml/prepare_regime_data.py --start 2010-01-01 --end 2026-10-01 --output-dir ml/data/research/my_new_snapshot
```

Thư mục đích phải chưa tồn tại. Script lưu phản hồi JSON gốc, CSV chuẩn hóa
của từng nguồn, timestamp, request, hash và đối chiếu trong `manifest.json`.
VCI là nguồn nền; KBS và VNDIRECT đối chiếu phần lịch sử chúng có. Không tự
chuyển nguồn khi request lỗi, không nối giá thiếu hay tự nội suy.

Khi có xung đột Close, chỉ chọn giá được ít nhất hai broker đồng thuận, hoặc
mốc đã đối chiếu báo cáo gốc trong `vnindex_source_review.json`. Mọi quyết định
được ghi từng ngày tại `index_source_decisions.csv`. Bất đồng chưa giải quyết
hoặc ngày xuất hiện ở nguồn khác nhưng ngoài lịch nguồn nền sẽ chặn snapshot.
Các broker có thể dùng chung feed, nên đồng thuận không chứng minh tính độc lập
của nguồn. Đoạn trước 01/06/2012 hiện chỉ có VCI trong ba nguồn này.

Hai ngày HOSE ngừng giao dịch 23–24/01/2018 được loại theo thông báo được dẫn
trong source review, thay vì coi giá lặp là hai phiên. Với ETF, ngày Close bất
đồng giữa hai broker được bỏ khỏi file ETF; lịch VNINDEX vẫn giữ đủ phiên thật.
Không lấy OHLC/volume từ các nguồn đang bất đồng để thêm feature vào index.

Có thể tái xử lý từ phản hồi đã lưu, không tải lại:

```bash
python3 ml/prepare_regime_data.py --start 2010-01-01 --end 2026-10-01 --from-snapshot ml/data/research/brokers_2010_20261001 --output-dir ml/data/research/my_replayed_snapshot
```

File `*.provenance.json` gắn nguồn với hash CSV cụ thể. Pipeline từ chối CSV
đã bị sửa nhưng provenance chưa được xây lại. File nguồn gốc không có provenance
vẫn được audit cấu trúc nhưng ghi rõ chưa xác minh nguồn.

Đọc kết quả điều tra và giới hạn tại [báo cáo dữ liệu](../docs/regime-data-review.md).

## File kết quả training

Mỗi lần chạy tạo `ml/reports/regime_v2/<UTC timestamp>/` riêng:

- `data_audit.json`: hash/source CSV, kiểm tra lịch/volume/gap, số mẫu, class
  counts và các ranh giới purge. Audit-only chỉ tạo file này.
- `regime_v2_report.json`: điểm validation dùng chọn cấu hình, phân biệt rõ
  `development_only`, `quick_development_only` và `final_holdout`.
- `model_comparison.png`: điểm development validation; không phải điểm test.
- Chỉ chế độ final mới có `holdout_predictions_t*.csv` và `models/*.onnx` nếu
  export thành công. Model thắng validation mới được chấm holdout. Không tự
  thay model khác khi export bị lỗi.

`--output-dir <thư-mục-mới>` đổi nơi lưu; thư mục phải chưa tồn tại. Model không
được ghi vào backend. Schema nghiên cứu `close-v3-research` (12 feature) và
`close-etf-v3-research` (16 feature) chưa được nối vào backend. Scaler Logistic
được nhúng trong ONNX, kiểm tra nhãn và xác suất native/ONNX trước khi ghi.

## Nhãn, purge và baseline

Nhãn T+H được tính trên lịch VNINDEX đầy đủ trước khi lọc feature thiếu, giữ
`label_end_date`; không dùng nhãn chưa hoàn tất. Các fold mở rộng theo thời gian,
purge mọi mẫu có `label_end_date >= validation_start`. Mỗi train fold cần ít
nhất 30 mẫu và đủ ba regime; `--splits` mặc định 4.

Trong chế độ final, development còn phải có `label_end_date < holdout_start`.
Ranh giới tự động dựa trên 80% đoạn lịch gốc đủ nhãn T+120; không thay khi đổi
subset horizon. Tuy nhiên, ranh giới đó vẫn phải qua kiểm tra exposure; dữ liệu
đã xem không được coi là test độc lập dù đổi dataset hoặc kéo dài lịch sử.

Optuna và chọn model/feature set dùng cùng các fold development nên điểm đó có
selection bias. Majority baseline lấy lớp đông nhất từ train; Macro F1 luôn
đếm đủ ba lớp. Nhãn horizon dài chồng lấn: số dòng không phải số quan sát độc lập.
Đây là đánh giá phân loại, chưa phải backtest lợi nhuận.

## Giới hạn xác minh

Audit từ chối ngày trùng, tương lai/cuối tuần, giá không hữu hạn/không dương và
OHLC sai nếu có các cột đó. Biến động >15%, gap dài và độ lệch lịch được ghi
lại, không tự cắt ngoại lệ. `Adj Close` được ưu tiên nếu có; ETF Close hiện vẫn
chưa được chứng nhận cách điều chỉnh cổ tức/chia tách, và không phải NAV/total
return series. Calendar broker được đối chiếu từng phần, chưa phải toàn bộ
lịch HOSE độc lập đã xác minh. Có lịch chính thức đủ cột `Date`, dùng `--calendar`.

Các sửa đổi ở đây chỉ áp dụng cho `train_regime_v2.py` và công cụ chuẩn bị dữ liệu
mới; notebook Colab, pipeline cũ và downloader ma trận cũ không nhận các thay đổi.

## Regression tests, không train model

```bash
python3 -m unittest discover -s ml -p 'test*regime*.py' -v
```

Các test điều phối dùng estimator giả; test ONNX dùng hệ số dựng trực tiếp,
không gọi train trên dữ liệu thị trường. Có kiểm tra causal feature, horizon qua
gap, correlation cùng phiên, purge, scaler, hash, xử lý xung đột và exposure.

## Thí nghiệm feature dài hạn và cửa sổ train

Dùng script riêng `ml/experiment_regime.py` để so sánh có kiểm soát sau lượt
`20261017T135531_744801Z`: giữ ngày validation/nhãn, tuning trong inner fold,
refit theo 63 phiên và so expanding/3y/5y. Nhóm feature trend/risk cùng báo cáo
báo giảm sai/bỏ lỡ được mô tả trong [hướng dẫn thí nghiệm](../docs/regime-experiments.md).
Script training cũ vẫn giữ nguyên; không tự chấm lại holdout hoặc deploy model.

## Thí nghiệm định nghĩa nhãn

Để so riêng nhãn T+20 ±5% và nhãn chuẩn hóa volatility, giữ LightGBM/trend/3y,
dùng `ml/experiment_regime_labels.py`. Công cụ giữ nguyên script/nhãn cũ và báo
cáo riêng native F1 với thước đo rủi ro −5% chung. [Hướng dẫn nhãn](../docs/regime-label-experiment.md).
