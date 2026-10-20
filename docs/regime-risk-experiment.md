# Thử nghiệm cảnh báo rủi ro T+20

Script `ml/experiment_regime_risk.py` so sánh ba LightGBM: nhãn ba lớp ±5%, nhãn ba lớp volatility và nhãn nhị phân giảm quá 5%. Cùng feature close-etf/trend, cửa sổ lịch sử 3 năm, ngày validation và lịch refit. Mục tiêu đánh giá chung: lợi suất đơn VNINDEX sau 20 phiên < −5%.

Đây là nghiên cứu development trên lịch sử đã xem. Không có tập test độc lập mới, không xuất ONNX hay cập nhật backend. Các nhãn và báo cáo cũ được giữ nguyên.

## Chạy

Tại thư mục gốc dự án, kiểm tra dữ liệu trước:

```bash
python3 ml/experiment_regime_risk.py \
  --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json \
  --audit-only
```

Chạy thử toàn pipeline bằng ngân sách nhỏ:

```bash
python3 ml/experiment_regime_risk.py \
  --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json \
  --quick
```

Chạy đủ: bỏ `--quick` (mặc định 15 trials, timeout 60 giây cho mỗi lần tune). Cần môi trường đã cài LightGBM và Optuna như các lần trước. Kết quả mỗi lần nằm trong `ml/reports/regime_risk/<timestamp>/`.

## Quy tắc thời gian và ngưỡng

Mỗi block dự báo lấy lịch sử có nhãn đã kết thúc trước ngày dự báo. Dành 20% cuối làm calibration, phần đầu làm core train; loại khỏi core các nhãn kết thúc từ ngày bắt đầu calibration trở đi. Giữ cùng lịch sử và phép chia cho cả ba model.

Chỉ tune ở core của block đầu mỗi outer fold, với các inner fold được purge. Cả ba ứng viên dùng cùng mục tiêu average precision của sự kiện giảm >5%; đây là thí nghiệm mới, không tái lập chính xác các model tune bằng native F1 cũ. Inner validation không có sự kiện giảm đóng góp AP=0 cho mọi trial; nếu toàn sự kiện giảm thì AP=1. Những fold này không phân biệt chất lượng xếp hạng. Không đổi ngày hay nhãn để ép đủ sự kiện.

Mỗi block fit model trên core rồi dùng chính model đó dự báo cả calibration và block tương lai. Không refit thêm calibration sau khi chọn ngưỡng, tránh đổi thang điểm. Ngưỡng là phân vị 90% của điểm calibration, cảnh báo khi điểm lớn hơn ngưỡng; xử lý điểm bằng nhau theo hướng ít cảnh báo. Mục tiêu 10% áp dụng trên calibration, tỷ lệ tương lai có thể khác. Vì giảm tập fit để dành calibration, điểm có thể thấp hơn thí nghiệm trước.

Điểm `predict_proba` từ model có balanced class weights được dùng làm điểm xếp hạng; không diễn giải 0,7 thành xác suất giảm 70%.

## Đọc kết quả

- `comparison.md` và `causal_metrics.csv`: TP/FP/FN, precision/recall, tỷ lệ cảnh báo thực tế, AP và ROC-AUC theo fold/tổng. AP so với prevalence cho biết mức xếp hạng vượt nền, không phải F1.
- `retrospective_equal_count.csv`: mỗi model đúng floor(10% × số ngày) cảnh báo mỗi fold, chọn điểm cao nhất trong toàn fold. So công bằng về số cảnh báo, nhưng dùng phân phối điểm tương lai: **chỉ là chẩn đoán xếp hạng, không phải quy tắc chạy thực tế hay backtest**.
- `year_metrics.csv`: xem giai đoạn nào model mất tác dụng.
- `paired_block_sensitivity.csv`: khoảng phân vị 2,5–97,5% của chênh lệch precision/recall so với fixed_5pct, dùng 1.000 lần bootstrap ghép cặp với block 20 và 60 phiên, lấy mẫu trong từng fold. Đây là kiểm tra độ nhạy có điều kiện trên thí nghiệm đã chọn, không loại bỏ thiên kiến do thử nhiều lần trên development. Không kết luận cải thiện chỉ vì một khoảng không chứa 0.
- `<policy>_predictions.csv`: điểm, ngưỡng lịch sử, cảnh báo và sự kiện thực tế từng ngày.
- `<policy>_refits.json`: ngày core/calibration, ngày nhãn kết thúc, ngưỡng và tham số, để kiểm tra thời gian.

Tìm ứng viên có precision/recall tốt ở số cảnh báo tương đương, kết quả đều qua fold/năm và không phụ thuộc một giai đoạn. Các nhãn T+20 chồng lấn: số TP là số mẫu ngày, không phải số đợt sụp độc lập. Chưa có mô phỏng giao dịch, phí hay lợi nhuận.

## Kiểm tra ngưỡng trượt và độ ổn định cây

Script hiện xuất thêm ngưỡng trượt 60 và 120 **quan sát feature hợp lệ**. Tại ngày t, model core hiện tại chấm lại chuỗi feature lịch sử; phân vị chỉ lấy điểm ở các ngày trước t và sau ngày cuối core train. Không trộn điểm của model cũ vào thang điểm model mới, không cần biết nhãn của ngày đang dự báo. Nếu thiếu đủ 120 quan sát quá khứ ngoài tập fit, preflight dừng. Khi dữ liệu có khoảng trống, số quan sát không nhất thiết bằng số phiên VNINDEX; không tự điền khoảng trống.

Lưu ý: phân vị trượt thích nghi theo lịch sử, **không đảm bảo tỷ lệ cảnh báo tương lai là 10–12%**. Nếu điểm liên tục tăng, tỷ lệ vượt ngưỡng có thể vẫn rất cao; nếu rủi ro cao kéo dài, ngưỡng có thể thích nghi lên cao và làm giảm cảnh báo. Vì vậy giữ cả ngưỡng tĩnh làm đối chứng, xuất tất cả cấu hình thay vì tự chọn cấu hình tốt nhất.

Chạy nhánh tune như trước (mặc định), hoặc thêm `--fixed-params` để cố định cây nông qua tất cả fold/refit, không chạy Optuna:

```bash
python3 ml/experiment_regime_risk.py \
  --reference-report ml/reports/regime_v2/20261017T135531_744801Z/regime_v2_report.json \
  --fixed-params
```

Bộ cố định: 150 cây, learning_rate=0.03, max_depth=3, num_leaves=7, min_child_samples=50, colsample_bytree=0.7, reg_alpha=0.1, reg_lambda=1, balanced weights, seed=42. Đây là phép kiểm tra độ nhạy đã định trước, không phải bộ tham số được khẳng định tối ưu. Cả ba định nghĩa nhãn đều được chạy. Muốn preflight riêng nhánh này thêm `--audit-only`.

Các file mới:

- `threshold_comparison.csv`: static / rolling_60 / rolling_120, theo fold và tổng, cùng thang đánh giá giảm >5%. Đây là kết quả ngưỡng dùng quá khứ, khác với `retrospective_equal_count.csv`.
- `<policy>_refits.json`: thêm số mẫu, mean, p90 và std điểm trên calibration; giữ cùng model khi so với block dự báo.
- `diagnostics/refit_drift.csv`: thống kê điểm calibration và dự báo theo model/refit. Không suy ra nguyên nhân kinh tế chỉ từ phân phối điểm.
- `diagnostics/fold_diagnostics.csv`: base rate, AP, AUROC và Spearman giữa score với **âm lợi suất T+20** (điểm cao nên đi với mức lỗ lớn). Điểm tính chung một fold có nhiều model refit là thống kê gộp, cần xem thêm theo refit.
- `diagnostics/fold3_positive_days.csv` và `fold3_price_diagnostics.png`: tất cả ngày thực tế giảm >5%, phân biệt bắt được/bỏ lỡ theo ngưỡng tĩnh. 36 ngày positive không đồng nghĩa 36 false negative.
- `fold3_feature_context.csv`: feature đã dùng ở từng ngày fold 3, kèm score và các ngưỡng; chỉ để chẩn đoán, không tự thêm feature mới.
- `diagnostics/positive_day_runs.csv`: các chuỗi ngày positive liên tiếp theo lịch VNINDEX. Các chuỗi cũng không phải các biến cố kinh tế độc lập.

Đọc lại báo cáo đã có mà **không train lại**:

```bash
python3 ml/regime_risk_diagnostics.py \
  --risk-dir ml/reports/regime_risk/20261017T152147_353782Z
```

Lệnh tạo thư mục `diagnostics` mới và từ chối ghi đè nếu đã tồn tại. Có thể dùng `--output-dir` với đường dẫn mới. Báo cáo cũ không lưu phân phối điểm calibration, nên không khôi phục được mean/std hoặc ngưỡng rolling chỉ từ một giá trị p90. Muốn có các cột đó phải chạy lại model bằng script đã cập nhật.

AP dưới base rate hoặc IC âm cảnh báo chất lượng xếp hạng trên mẫu đang xét, chưa chứng minh feature inversion, lý do vĩ mô hay SHAP đảo chiều. Không tự đảo dấu score sau khi nhìn fold 3. Pipeline đã purge bằng ngày kết thúc nhãn và chỉ tune một lần mỗi outer fold; không thêm một khoảng embargo tùy ý để chữa một lỗi chưa được xác nhận. Chưa thêm OHLC/volume/exhaustion vì cần nguồn dữ liệu được kiểm chứng và một thí nghiệm feature riêng.
