# F1 research, vòng 3 — 19/10/2026

Mốc cao nhất mới là **51,2149% mean fold macro F1**, trên cùng 1.560 phiên T+20 và cùng nhãn động ±1 sigma. Mốc ban đầu của bài toán nhãn động là 48,9309%; chênh lệch **+2,2840 điểm phần trăm**. Đây là kết quả DEVELOPMENT đã được xem nhiều lần, chưa phải test độc lập hay hiệu quả đầu tư.

| Phương án | Mean F1 | Worst fold F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| Dynamic blend ban đầu |48,93%|40,00%|29,46%|43,10%|0,2622|
| Mốc vòng 2, mature-OOF adaptive fusion |49,73%|39,74%|32,33%|42,44%|0,2672|
| Matched-inner robust calibration |50,85%|37,70%|32,25%|45,64%|0,2847|
| Inner anchor + causal adaptation |50,53%|38,25%|34,52%|43,00%|0,2682|
| Block density bagging, adaptive |47,67%|39,63%|31,80%|37,96%|0,2273|
| **RandomForest density shrink** |**51,21%**|**39,11%**|**31,65%**|**47,84%**|**0,2959**|
| ExtraTrees density shrink |49,94%|38,05%|30,05%|45,87%|0,2771|

F1 là trung bình macro F1 của bốn fold 390 phiên, không phải tỷ lệ dự đoán đúng. F1 từng lớp cũng là trung bình bốn fold. F1 của RandomForest shrink theo fold: **56,01%; 66,31%; 39,11%; 43,43%**. Worst fold thấp hơn bản dynamic ban đầu khoảng0,89 điểm; so với matched robust thì bear F1 giảm khoảng0,60 điểm. Không gọi đây là cải thiện mọi mặt.

## Cách phối hợp

- Hai classifier LightGBM: trend có thông tin bổ sung chọn bằng purged inner folds và risk; lấy trung bình hai score.
- Ensemble hồi quy phân vị LightGBM: năm seed × hai target (log return thô / chia sigma) × chín phân vị, tổng90 regressor mỗi lần refit. Chuyển phân phối thành ba lớp theo ngưỡng sigma ở ngày dự đoán, cân bằng theo prior training.
- Hai RandomForestRegressor 300 cây, depth6, min leaf30, feature fraction0,7: học hai target lợi suất trên. Phân phối tại một dự đoán là trung bình phân phối lợi suất các mẫu huấn luyện đã mature trong từng lá, mỗi cây có trọng số bằng nhau. Với target thô, ngưỡng là ±sigma ngày dự đoán; với target chuẩn hóa là ±1. RF bootstrap dùng để học cấu trúc cây, phân phối lá dùng mọi mẫu train mature rơi vào lá đó.
- Lấy một nửa score density cũ và một nửa density Random Forest; phối hợp với classifier theo hệ số đã chọn trước mỗi outer fold bằng inner robust criterion. Trộn 50/50 score hiện tại và causal EMA5. Scores dùng ra quyết định, chưa phải xác suất đã hiệu chỉnh.

RandomForest density, tỷ lệ trộn và tham số được ghi trước khi xem kết quả outer của nhánh này. Hệ số classifier/density lấy từ nghiên cứu calibration trước đó: đó là một nhánh diagnostic có điểm outer đẹp hơn nhánh primary, nên việc tiếp tục dựa vào nó tạo thêm selection exposure. Không che giấu chi tiết này.

## Các thử nghiệm đã hoàn tất

1. Matched-cadence inner calibration: ba inner periods mỗi outer, refit63 phiên ngay trong inner period; tái huấn luyện cả classifier và toàn bộ ensemble density. Primary macro đạt49,13%; robust diagnostic50,85%; shrink49,37%.
2. Causal adaptive fusion lấy inner coefficient làm anchor: primary50,53%, secondary49,80%; không vượt anchor.
3. Moving-block bagging20 phiên, năm seed: primary47,67%, shrink49,14%; không cải thiện.
4. Empirical forest density: RandomForest shrink51,21%; full replacement48,96%; ExtraTrees shrink49,94%, replacement48,01%. Không chọn diagnostic full replacement đẹp nhất sau khi xem outer.

So với dynamic blend ban đầu, khoảng paired circular-block bootstrap của chênh lệch mean F1 là [0,00074;0,04490] với block20 và [0,00114;0,04683] với block60. So với mốc49,73%, block20 vẫn chứa0 ([-0,00204;0,03198]). So với50,85%, cả hai khoảng đều chứa0. Các khoảng mô tả lịch sử đã được lựa chọn/nghiên cứu nhiều lần; chưa hiệu chỉnh multiple testing và không chứng minh ưu thế độc lập.

Chưa có ứng viên qua toàn bộ multi-metric screen cũ (bao gồm không giảm worst/directional F1). Giữ các ứng viên nghiên cứu; không tự triển khai hoặc thay modelbackend. Goal cải thiện chất lượng vẫn active; không biến thiếu test tương lai thành lý do ngừng nghiên cứu offline.

## Kiểm chứng và tái lập

234 kiểm thử phần mềm đều qua. Audit độc lập tính lại nhãn từrawClose, endpoints T+20, F1/MCC, scoreargmax và bốn fold trên23 forecast files;34 hash nguồn khớp. Tái lập riêng cách tính inner EMA và chọn hệ số của cả4 outer folds.36 lần refit inner,112 lần fit forest và280 records bagging đều có endpoint nhãn train trước ngày dự đoán. Xem `independent_metric_audit.json`; đây là kiểm tra bằng triển khai khác trên cùng dữ liệu, không phải independent data test.

Nhãn luôn tính từ log return T+20 so với std20 của daily log return (ddof1) ×sqrt20, equality=sideway. Không sửa nhãn, bỏ phiên đánh giá, chọn seed bằng outer hay dùng giá điền ngược. Một metadata amendment của calibration chỉ làm rõ nhãn tham chiếu±5% được kế thừa; nó được ghi trước outer scoring và không đổi phép tính. Receipt nằm trong report calibration.

Để chạy lại nhánh forest với component archives đã lưu:

```bash
python3 ml/experiment_regime_empirical_forest.py
```

Script tự kiểm hash nguồn, dùng cùng target/cohort và in thư mục report mới. Để kiểm lại toàn bộ kết quả vòng này:

```bash
python3 ml/reports/regime_research/f1_goal_20261019_stage3/recalculate.py
PYTHONPATH=ml python3 -m unittest discover -s ml -p 'test*regime*.py'
```

Nguồn kết quả:

- `ml/reports/regime_matched_calibration/20261019T064830_252658Z/`
- `ml/reports/regime_anchored_fusion/20261019T065633_437477Z/`
- `ml/reports/regime_block_density/20261019T065257_068617Z/`
- `ml/reports/regime_empirical_forest/20261019T070202_443313Z/`

Bước nghiên cứu tiếp theo: xây dự báo inner cho chính empirical forest, rồi chọn tỷ trọng phối hợp bằng inner forecasts thay vì dùng nguyên anchor của density cũ. Chốt grid nhỏ trước khi chạy; giữ nguyên nhãn và toàn bộ outer dates.
