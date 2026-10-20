# Native model và kiểm tra thêm hai hướng cải thiện

Đợt này tạo được bộ model chạy độc lập cho `shock_shrink`, không chỉ replay điểm dự báo trong CSV. Mốc cao nhất của nghiên cứu vẫn là `analog_shrink` F1 51,4488%; bản ưu tiên về fold yếu hơn là `shock_shrink` 51,3745%, worst fold 40,3056%. Cùng ba lớp VNINDEX T+20 theo ±1 sigma, cùng 1.560 ngày/four folds. Tất cả điểm số là historical development đã được xem nhiều lần, chưa phải kết quả độc lập.

## Các thử nghiệm mới

| Phương án | Mean macro F1 | Worst fold F1 | Kết luận |
|---|---:|---:|---|
| Analog incumbent | 51,4488% | 39,3661% | Giữ mốc cao nhất |
| Close-only analog, ngày train cũ | 51,1428% | 39,0553% | Không thay incumbent |
| Close-only analog, thêm lịch sử từ 2010 | 51,4306% | 39,3511% | Không thay incumbent |
| Shock incumbent | 51,3745% | 40,3056% | Giữ ứng viên cân bằng |
| Forest có thêm supervision min/max đường giá tương lai | 51,1191% | 40,3056% | Không thay incumbent |

Analog có đối chứng cùng ngày train để tách ảnh hưởng bỏ feature ETF khỏi ảnh hưởng thêm lịch sử. k100, hai feature views, tỷ trọng half-component được giữ cố định. Không tạo giá ETF trước khi có dữ liệu.

Path forest chỉ dùng đường giá tương lai làm mục tiêu huấn luyện trên các mẫu đã hoàn tất trước thời điểm refit. Đầu vào dự đoán không có đường giá tương lai. Min/max dùng toàn bộ 20 phiên trên lịch gốc; đoạn cuối thiếu giá phải là NaN. Đích đánh giá cuối kỳ vẫn giữ nguyên, không đổi nhãn để tăng điểm.

## Bộ native

Snapshot `ml/artifacts/regime_shock_candidate_20261019T090555_259289Z` gồm 2 classifier LightGBM, 90 quantile LightGBM, 8 Random Forest, các mẫu lợi suất trong lá và kho analog compact/full kèm median/IQR. Bộ tạo đặc trưng giữ cả 20 phiên cuối chưa có nhãn. Đối chiếu toàn bộ các bảng đặc trưng nghiên cứu, sai số bằng 0.

Snapshot được fit tại mốc dữ liệu 01/10/2026 và tạo ngày 19/10; preview của snapshot không phải dự báo đã ghi nhận trong quá khứ hay dự báo độc lập. Các nhãn huấn luyện kết thúc trước mốc refit. Cấu hình giữ lựa chọn fold cuối, không tune thêm theo điểm vừa xem. Dữ liệu cũ 18 ngày; CLI `--require-fresh` đã từ chối đúng. Chưa thay model của web.

Historical native replay đã hoàn tất tại `ml/reports/regime_shock_native/20261019T090304_754869Z/summary.json`: đủ1.560ngày/28blocks, mọi nhãn dự đoán khớp, F1 bằng51,3745%. Audit độc lập từ giá Close gốc và file dự đoán đã đạt; sai số score lớn nhất3,3306690738754696e-16. Đã kiểm tra checksum2.828payload native và84receipt cohort huấn luyện, gồm cutoff nhãn trước refit. Đây là parity/code audit trên lịch sử, không phải kiểm chứng ngoài mẫu mới.

## Điểm số và xác suất

Một logistic calibrator cố định, học từ tối đa504score quá khứ có nhãn trưởng thành, refit mỗi20phiên; yêu cầu ít nhất120mẫu và10mẫu/lớp. So trên cùng1.340ngày có calibrator; các ngày warmup không bị loại riêng theo chất lượng dự báo:

| Phương án | Brier (thấp tốt hơn) | Log loss (thấp tốt hơn) |
|---|---:|---:|
| Score gốc của shock | 0,52765 | 0,90394 |
| Tần suất lớp504nhãn VNINDEX đã biết | 0,55972 | 0,96955 |
| Logistic calibration | 0,53369 | 0,93788 |

Logistic không cải thiện tổng thể. Riêng fold3, cả score gốc và logistic đều thua prior về Brier. Đây là chẩn đoán chất lượng xác suất trên lịch sử, không chứng nhận score đã được hiệu chỉnh. Point policy không đổi; không gắn “độ tin cậy” theo phần trăm vào UI.

Hai đối chứng đơn giản trên cùng1.560ngày: momentum20 so với sigma hiện tại đạt F1 37,6059%; giữ trạng thái của chu kỳ20phiên vừa hoàn tất đạt37,9343%. Cả hai dùng giá đã biết tại thời điểm đóng cửa. Các đối chứng giúp diễn giải51%, không biến development thành test độc lập.

## Kiểm tra và chạy lại

Năm test mới đã đạt: save/load bộ native, checksum payload, nhãn trưởng thành, strict-tail/equality của phân phối lá, EMA qua restart/cuối tuần/thiếu phiên, trạng thái sai/phiên lặp, và complete future-path targets. Đây là kiểm tra code, không phải bằng chứng về lợi nhuận hay hiệu quả tương lai.

```bash
python3 -m unittest discover -s ml -p 'test_regime_shock*.py' -v
python3 -m unittest discover -s ml -p test_regime_path_forest.py -v
python3 ml/predict_regime_shock.py \
  --bundle ml/artifacts/regime_shock_candidate_20261019T090555_259289Z/native \
  --parameters 0.75 0.75 1.5
```

Sau khi historical replay hoàn tất:

```bash
python3 ml/reports/regime_research/f1_goal_20261019_stage7/recalculate.py
```

Report mới: `regime_close_history_analog/20261019T090704_554220Z`, `regime_path_forest/20261019T091101_051315Z`, `regime_shock_probabilities/20261019T090829_984153Z`. Audit và kiểm tra số liệu độc lập dùng cùng lịch sử; không phải independent test.

Bước tiếp theo phục vụ web: dữ liệu mới có dấu vết nguồn, quy tắc refit/chọn cấu hình cố định, lưu dự báo thực sự trước khi biết kết quả, kiểm tra độ ổn định qua các giai đoạn và đánh giá xác suất riêng. Chưa có cơ sở nói mô hình đã đạt chất lượng tốt nhất có thể hoặc sẵn sàng điều chỉnh danh mục tự động.
