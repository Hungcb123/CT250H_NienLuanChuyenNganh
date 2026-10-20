# F1 research vòng 4 — 19/10/2026

Mốc mean fold macro F1 cao nhất mới **51,3398%**, trên cùng 1.560 phiên T+20, bốn fold390 phiên và nhãn động±1sigma. So với51,2149%, tăng **0,1249 điểm phần trăm**; khoảng bất định còn chứa0 nên chưa xác nhận lợi thế dự báo thật. Goal vẫn active; không thay model ứng dụng.

| Phương án | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| Đối chứng RandomForest density shrink |51,21%|39,11%|31,65%|47,84%|0,295854|
| Chọn phối hợp bằng inner robust |47,71%|35,54%|26,69%|43,34%|0,252713|
| Chọn phối hợp bằng inner macro |49,53%|35,54%|31,53%|43,51%|0,266950|
| **Thêm forest học đồng thời return/magnitude** |**51,34%**|**39,25%**|**32,29%**|**47,36%**|**0,295870**|
| Thay toàn bộ forest bằng return/magnitude forest |50,78%|38,70%|32,02%|46,14%|0,285966|
| Thêm soft-margin density |50,58%|37,73%|31,37%|46,78%|0,286611|
| Soft-margin thay toàn bộ density, diagnostic |46,32%|35,75%|28,55%|42,25%|0,238805|

F1 không phải accuracy; các F1 trong bảng là trung bình theo bốn fold. Mốc mới có foldF1 **55,54%; 67,05%; 39,25%; 43,52%**. Thắng đối chứng3/4fold nhưng mức tăng nhỏ; bear tăng0,6463điểm, bull giảm0,4814điểm. So với dynamic blend ban đầu48,9309%, mean tăng2,4089điểm nhưng worst vẫn thấp hơn40,0013% ban đầu. Không gọi là tốt hơn mọi mặt.

## Các thay đổi đã thử

**Matched inner forest calibration.** Tái huấn luyện hai RandomForestRegressor raw/normalized tại36biên refit63phiên bên trong12innerperiods; train expanding, chỉ lấy nhãn có endpoint trước ngày dự đoán. Ghép với classifier/quantile inner forecasts đã lưu. Grid cố định5tỷ trọngforest×45hệ số/temperature=225ứng viên/outerfold. Chọn robust hoặc macro bằng inner scores của pipeline đãEMA, có penalty và ngưỡng đổi0,005 quanh bản cũ. Kết quả outer kém hơn dù inner chọn tốt hơn; không tiếp tục dùng bản chọn mới. Dự báo inner được lưu để tái sử dụng, không phải huấn luyện lại toàn bộ chỉ để thử rule khác.

**Joint return/magnitude forest.** Giữ nguyên300cây, depth6, leaf30 và các tham số forest cũ. Mỗi cây hồi quy có hai đầu ra `[r,abs(r)]`, hoặc `[r/sigma,abs(r/sigma)]`; chuẩn hóa từng đầu ra theo mean/std(ddof1) của chính tập train mature. Học multi-output để phép chia cây phản ánh cả mức lợi suất lẫn độ lớn biến động. Phân phối trong lá vẫn lấy lợi suất scalar gốc, không lấy target đã biến đổi hoặc đổi nhãn đánh giá. Đây là giả thuyết có kiểm chứng đối chứng, không phải khẳng định rừng học được volatility đúng.

Density cuối của nhánh tốt nhất là **50% ensemblequantile +25%forestmean cũ +25%forestmean/magnitude**. Mỗi density dùng trung bình hai đầu raw/normalized; giữ classifiertrend/risk, hệ sốinneranchor đã chốt trước outerfold, và current/EMA5 bằng nhau. Tham số/hệ sốmới được ghi trước khi chấm outer của nhánh này. Score đã cân bằng dùng chọn lớp, chưa phải xác suất được hiệu chỉnh.

**Distance-aware soft supervision.** Cố địnhwidth0,25, với `z=forward_log_return/sigma`, targetsoftbear=`sigmoid((-1-z)/width)`, softbull=`sigmoid((z-1)/width)`, softside=phần giữa; baLightGBMregressor squared-error thay vì hardclassification. Nhãn chấm điểm vẫn±1sigma cũ. Nhánhshrink25%softdensity thấp hơnđối chứng; không dùng.

Probe đầu của nhánhsoft dừng do triệt tiêu số học khi tính `1-bear-bull`, sau một số trainingblocks nhưng trước hoàn tất forecastexport hoặc aggregateouterscoring. Đã lưu failedsourcevàreceipt trong `regime_soft_margin/20261019T071229_367729Z/`. Run hợp lệ mới dùng công thức intervalmass tương đương dạng tích cácsigmoid, luôn không âm, chuẩn hóa lại. Không đổiwidth,learner,grid hoặcnhãn. Hai regressiontests xác nhậngiá trịcựcđoan và khớpCDF/SFlogistic độc lập.

## Bằng chứng và giới hạn

Paired circular-block bootstrap của nhánh tốt nhất trừ51,21%: block20códelta0,001249, khoảng[-0,005919;0,007824]; block60[-0,004466;0,005751]. Đây là phân tích mô tả trên lịch sử đã nghiên cứu nhiều lần, không hiệu chỉnhmultiple-testing và không phải test độc lập. Chưa qua multi-metricscreen cũ; không tuyên bố được nâng cấp triển khai.

Audit độc lập:

- Tính lại labels/endpoints từrawClose vàmetrics của10forecastfiles, mỗi fileđủ1.560ngày và4×390rows.
- Xác minh49sourcehashes và strictmaturity tại36innerforestrefits,56magnitude-forestfitrecords,28softheadrefits.
- Tính lại225innercandidate scores, penalty vàlựa chọn của4outerfold bằngsklearnmetrics vàpandasEMA.
- Dựng lại cả10scorepipelines từcomponentarchives bằng công thức độc lập; sai số lớn nhất3,33e-16.
- Bảy kiểm thử trọng tâm đãqua (5vềempiricalleaf/bagging/EMA và2vềstableCDF). Fullsuite234đãqua ởvòngtrước; các hàm/sources cũ đượcpin không sửa. Không dùng kiểm thử phần mềm để thay bằng chứng dự báo.

Xem `independent_metric_audit.json`. Audit triển khai độc lập vẫn dùng cùng dữ liệu, không biếndevelopment thànhtest.

Chạy lại nhánh tốt nhất:

```bash
python3 ml/experiment_regime_magnitude_forest.py
```

Kiểm lại kết quả vòng này:

```bash
python3 ml/reports/regime_research/f1_goal_20261019_stage4/recalculate.py
PYTHONPATH=ml python3 -m unittest test_regime_empirical_forest test_regime_anchored_bagging test_regime_forecast_smoothing test_regime_soft_margin -v
```

Reports:

- `ml/reports/regime_inner_forest/20261019T070804_899122Z/`
- `ml/reports/regime_magnitude_forest/20261019T070928_701705Z/`
- `ml/reports/regime_soft_margin/20261019T071331_554457Z/`

Bước tiếp theo: thử thông tin bổ sung đã qua source/timingreview cho chính forestdensity, với groupchọn từinnerclassifier trướcouterboundary, không chọngroup theoouterF1. Đây là một thay đổi đầu vào khác với thêm model/hệ số trên cùngfeaturecũ.
