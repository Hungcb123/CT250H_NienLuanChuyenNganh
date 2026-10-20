# Nghiên cứu F1, vòng 5 — 19/10/2026

Hoàn tất ba thử nghiệm trên cùng 1.560 phiên T+20, bốn fold 390 phiên và nhãn động ±1 sigma. **Mean fold macro F1 cao nhất là 51,4488%**. Có thêm một ứng viên cân bằng hơn: **51,3745% mean F1 và 40,3056% worst fold F1**. Chưa xác nhận ưu thế độc lập hoặc thay model ứng dụng; goal vẫn active.

| Phương án | Mean F1 | Worst fold F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| Đối chứng vòng 4 |51,34%|39,25%|32,29%|47,36%|0,2959|
| Thêm forest dùng nhóm thông tin đã chọn |49,00%|38,20%|28,16%|45,38%|0,2688|
| Thay phần forest bằng forest dùng nhóm thông tin |48,69%|39,25%|28,01%|44,36%|0,2678|
| Toàn bộ thông tin, diagnostic |50,01%|38,84%|29,88%|46,02%|0,2822|
| **Thêm 25% density từ phiên tương tự** |**51,45%**|39,37%|32,02%|47,99%|0,2978|
| Thêm 50% density từ phiên tương tự |51,04%|38,09%|31,15%|47,91%|0,2920|
| **Thêm 25% density từ forest có đặc trưng cú sốc** |**51,37%**|**40,31%**|31,42%|48,35%|**0,3005**|
| Thêm 50% density từ forest có đặc trưng cú sốc |50,85%|39,25%|31,09%|47,57%|0,2915|

Đây là macro F1 trung bình bốn fold, không phải accuracy. F1 từng lớp cũng tính trung bình theo fold. Biểu đồ `comparison.png` thể hiện từng fold, không dùng một điểm trung bình để che độ biến thiên.

## Ba giả thuyết đã kiểm tra

**Thông tin bổ sung cho forest.** Giữ nguyên tham số 300 cây, depth6, leaf30, hai kiến trúc mean/magnitude và hai target raw/normalized. Nhóm thông tin lấy nguyên lựa chọn inner classifier đã có trước mỗi outer boundary: VIX, indices, control, OHLCV cho các fold 1–4. Chạy thêm toàn bộ nhóm kết hợp làm diagnostic, không chọn nhóm bằng outer F1. Trường xung đột/không sẵn có giữ NaN và dùng nhánh missing native của sklearn1.7; không điền giá hoặc bỏ ngày đánh giá.

`context_forest_replace` giữ tỷ lệ quantile/forest bằng 50/50 để kiểm tra việc thay đầu vào của forest. `context_shrink` là một công thức khác đã ghi trước khi chấm điểm: 75% density hiện có +25% forest mới; nó đồng thời tăng tổng tỷ trọng forest. Vì vậy không diễn giải riêng nhánh shrink như một phép thay feature thuần túy. Cả hai đều kém hơn đối chứng. Ở fold3 có lựa chọn control, bốn component forest mới tái lập đúng component cũ trên390 ngày; điều đó không buộc toàn bộ công thức shrink có score bằng đối chứng.

VIX giữ độ trễ observation+2 ngày lịch và giới hạn stale7 ngày; OHLCV/indices chỉ nhận giá trị được các nguồn broker đồng thuận. Những kiểm tra này không chứng nhận được lịch sử phát hành/vintage độc lập. `context_source_plan` trong plan là metadata của helper tạo feature, kế thừa nhãn tham chiếu±5%; actual training/evaluation đã relabel sang±1sigma ở top-level và được audit lại từrawClose.

**Phân phối lợi suất từ phiên tương tự.** Chuẩn hóa feature bằng median/IQR của tập train mature, rồi lấy100 láng giềng theo Euclidean; hòa khoảng cách theo thứ tự train ổn định. Gaussian weights dùng median khoảng cách trong nhóm đã chọn làm bandwidth. Nếu bandwidth=0, chỉ dùng láng giềng trùng hoàn toàn; IQR=0 được thay bằng1. Không fit scaler trên validation và không dùng SciPy standardized-distance mặc định có thể gộp cả hai tập.

Lấy trung bình hai feature views:19feature gốc và6feature gọn (`ROC_20`, `ROC60`, `DistSMA200`, `HV_20`, `ETF_ReturnSpread20`, `RSI_14`). Mỗi view có phân phối raw return và return/sigma; raw được chấm với ngưỡng±sigma ở ngày dự đoán, normalized với±1. Equality=sideway, chia prior training theo cùng quy tắc decision score cũ. Pipeline cao nhất dùng25% analog density và75% density cũ, cùng classifier, inner anchor và current/EMA5. Không chọn k, bandwidth hoặc tỷ trọng bằng outer search.

Mean F1 tăng0,1090 điểm so với51,3398%; worst tăng0,1197 điểm, bull tăng0,6306 điểm, bear giảm0,2689 điểm. Bốn fold là **56,37%; 66,73%; 39,37%; 43,33%**. Khoảng paired circular-block của chênh lệch mean F1: block20[-0,008161;0,009605], block60[-0,008292;0,008293]. Cả hai chứa0; không tuyên bố lợi thế chắc chắn.

**Đặc trưng cú sốc cho forest.** Tái sử dụng hàm `directional_features` đã có, không sửa code nguồn được pin: momentum3/5/10/20/60 đã chuẩn hóa, shock hiện tại/trễ, downside energy, tỷ trọng phiên giảm, vol5/20, drawdown20/60, skew và acceleration. Giữ tham số, bốn head forest và các classifier/anchor cũ. Tỷ trọng mới chốt trước khi chấm là25% hoặc50% density mới trên nền analog-shrink. Nhánh25% có worst fold tốt hơn, dù mean thấp hơn mốc cao nhất0,0743 điểm. Bốn fold là **56,43%; 65,44%; 40,31%; 43,33%**.

## So với lúc bắt đầu goal

Mốc lúc bắt đầu goal được ghi ở README vòng1 là49,2508% mean,40,0013% worst,29,0485% bear,44,1610% bull và0,26835MCC. Nhánh shock25% hiện đạt51,3745% mean,40,3056% worst,31,4176% bear,48,3456% bull và0,30052MCC; thắng **4/4fold**.

Như vậy nhánh này qua point screen so với mốc đầu goal (+2,1237 điểm mean F1, tăng worst/MCC và hai lớp hướng). Tuy nhiên block20CI của chênh lệch vẫn chứa0 rất nhẹ: **[-0,000257;0,038300]**, còn block60[0,001029;0,039389]. Không tăng số lần bootstrap hoặc đổi seed để cố biến cận dưới thành dương. So sánh này không thay thế các screen thất bại so với incumbent có mean cao hơn ở vòng sau. Xem `goal_start_comparison.json`.

Tất cả lịch sử đã được nghiên cứu nhiều lần. Các khoảng bootstrap là mô tả, chưa điều chỉnh việc chọn mô hình qua nhiều thử nghiệm và không tạo ra một tập test độc lập. Chưa chấp nhận triển khai.

## Kiểm chứng

23 kiểm thử trọng tâm về nguồn, độ trễ, consensus, feature cú sốc, empirical forest và analog đều qua. Test mới xác nhận thêm các query cực đoan không thể làm thay đổi scaler hoặc score của query trước; các feature trùng hoàn toàn/zero-IQR vẫn cho mass hợp lệ và equality neutral.

Audit triển khai độc lập đã kiểm:

- Cùng nhãn/endpoints từrawClose, đúng1.560ngày và4×390rows trong10forecastfiles.
- 49sourcehashes;448fit records đều có endpoint train trước prediction boundary (224context,112analog,112shock).
- VIX availability/staleness và component parity của control fold.
- Dựng lại cả10pipeline phối hợp/EMA bằng công thức riêng vàpandasEMA; sai số score lớn nhất2,22e-16.
- Dựng lại bằng NumPy broadcast distances cả bốn analog views/targets ở block đầu63phiên; score khớp1e-12.

Xem `independent_metric_audit.json`; đây là triển khai audit khác trên cùng dữ liệu, không phải independent data test.

Chạy lại hai nhánh đáng giữ để nghiên cứu:

```bash
python3 ml/experiment_regime_analog_density.py
python3 ml/experiment_regime_shock_forest.py
```

Kiểm lại kết quả và vẽ biểu đồ:

```bash
python3 ml/reports/regime_research/f1_goal_20261019_stage5/recalculate.py
python3 ml/reports/regime_research/f1_goal_20261019_stage5/plot_comparison.py
```

Reports:

- `ml/reports/regime_information_forest/20261019T071622_321945Z/`
- `ml/reports/regime_analog_density/20261019T071721_721598Z/`
- `ml/reports/regime_shock_forest/20261019T072038_455776Z/`

Bước nghiên cứu tiếp theo: kiểm tra geometry của analog distance (covariance chỉ fit trên train, tránh đếm lặp các chỉ báo tương quan) và analog có khoảng cách thời gian tối thiểu20phiên để giảm tập trung vào các nhãn T+20 chồng lấn. Giữ target/cohort và chốt quy tắc trước khi chạy. Chưa có native inference bundle cho các ứng viên mới; các snapshot hiện tại là dự báo nghiên cứu và recipe tái lập, không tự coi là model triển khai.
