# Kiểm tra lại mục tiêu dự báo 3 lớp

Đợt ngày18/10 quay lại bài toán T+20 cố định ±5%, không dùng giảm cảnh báo rủi ro để thay thế mục tiêu 3 lớp. Chủ nhật chỉ ảnh hưởng lịch thu dự báo mới; vẫn có thể train và kiểm tra lịch sử.

Đã chạy10 cấu hình shallow GBM/logistic/ordinal × cửa sổ3y/expanding và6 cấu hình tái dùng tham số tune cũ (trend/risk/equal × refit63/20). Mỗi cấu hình dùngargmax và quy tắc trọng số macro-F1 nhân quả: tổng32 biến thể quyết định. Tất cả cùng1.560 ngày và cùng nhãn.

Tham số cũ được chọn trong purged inner CV trước từng outer fold; tái dùng nguyên vẹn, không tune lại trên outer labels. Cả hai bảntrend/risk refit63 tái lập đúng1.560/1.560 dự đoán cũ. Mọi nhãn train và nhãn lịch sử dùng học trọng số đều phải kết thúc trước ngàyrefit.

| Cấu hình / quyết định | Mean fold macro F1 | Worst fold F1 | Mean MCC | Pooled macro F1 |
|---|---:|---:|---:|---:|
| legacy_trend_63/argmax | 0.3860 | 0.3728 | 0.1108 | 0.4294 |
| legacy_risk_63/argmax | 0.3898 | 0.3341 | 0.1383 | 0.4216 |
| legacy_equal_63/argmax | 0.3957 | 0.3600 | 0.1437 | 0.4332 |
| legacy_equal_20/argmax | 0.3793 | 0.3615 | 0.1061 | 0.4130 |
| gbm_balanced_expanding/argmax | 0.3666 | 0.3347 | 0.0669 | 0.3927 |
| ordinal_unweighted_expanding/argmax | 0.3320 | 0.2544 | 0.0476 | 0.3662 |

Mean fold macro F1 lấy trung bình F1 của4 giai đoạn, còn pooled macro F1 gộp tất cả dự đoán rồi tính một lần. Hai đại lượng không bằng nhau; không được lấy pooled F1 mới so với mean fold F1 cũ để nói model cải thiện.

Kết quả: không biến thể nào qua điều kiện cải thiện so với cả hai bản cũ (+0,02 mean F1, không giảm worst F1, tăng MCC, thắng ít nhất3/4 folds). Ensemble tăng nhẹ lên0,3957 nhưng worst F1 thấp hơn bảntrend; các khoảng paired block bootstrap20/60 phiên của chênh lệch F1 đều chứa0. Chưa nhận là mô hình tốt hơn rõ rệt.

Ma trận bảntrend cũ vẫn có đủ3 cột dự đoán: không có bằng chứng model chỉ đoán một lớp. Precision/recall lớp giảm còn yếu; cân bằng lớp sẵn có không tự giải quyết được. Các thử bỏ cân bằng, ordinal, tăng refit và điều chỉnh quyết định không đủ.

Bước tiếp theo về nghiên cứu: thử chuyển giao dữ liệu từ lịch sử VN30/VNMID/VNSML đã đối chiếu nguồn, với feature tương đối và chia theo thời gian chung cho mọi chỉ số. Phải có đối chứng VNINDEX-only cùng feature/model, cân trọng số theo ngày để không coi chỉ số tương quan là mẫu độc lập, và giữ nguyên nhãn/ngày kiểm chứng. Không gộp rổ cổ phiếu hiện tại như thể là universe point-in-time.

Artifacts:

- `ml/reports/regime_multiclass/20261018T151435_412098Z`
- `ml/reports/regime_multiclass_reuse/20261018T151747_040696Z`
- `combined_audit.json`: đối chiếu ngày/nhãn, kiểm tra xác suất và thời gian nhãn ở từng lầnrefit.
- `paired_sensitivity.json`: độ bất định của ensemble so với từng đối chứng. Đây là development đã được xem nhiều lần, không phải bằng chứng test độc lập.
- Không sửa ứng viên risk đã đóng băng hoặc model production.


## Đợt học chung chỉ số đã chạy

Đã thử8 cấu hình: shallow/medium GBM ×3y/expanding ×VNINDEX-only/pooled VN30,VNMID,VNSML. Mỗi cách dùng cùng12 đặc trưng tương đối và1.560 ngày kiểm chứng cũ. Nhãn được dịch trên lịch VNINDEX đầy đủ trước khi lọc; không bfill. Cân trọng số theo ngày trước chi phí lớp, sau đó tính chi phí lớp bằng khối lượng trọng số thay vì đếm các dòng chỉ số tương quan.

| Lịch sử / cây | F1 VNINDEX-only | F1 pooled | Chênh lệch |
|---|---:|---:|---:|
|3y / shallow|0.3386|0.3220|-0.0166|
|3y / medium|0.3440|0.3436|-0.0004|
|expanding / shallow|0.3717|0.3578|-0.0140|
|expanding / medium|0.3802|0.3675|-0.0127|

Cả4 bản pooled đều không tăng mean fold F1, không bản nào qua screen so với đối chứng cùng feature/model/window. Không nhận hướng này làm cải thiện. Thêm dòng dữ liệu tương quan không tự làm dự báo tốt hơn.

Artifacts: `ml/reports/regime_panel/20261018T152634_420727Z/`. `causal_audit.json` kiểm tra đúng ngày/nhãn cũ, xác suất hợp lệ, thời gian nhãn và cân trọng số qua mọi lầnrefit. Lỗi tên trường metadata `pooled` trùng dictionary metric đã được sửa ở phần báo cáo; dự đoán đã hoàn tất được giữ nguyên và tái lập báo cáo, không train lại. Bằng chứng và hash hàm train nằm trong `reporting_repair.json`.

Hướng nghiên cứu tiếp: kiểm tra thông tin OHLCV đồng thuận, VIX lag và chênh lệch nhóm chỉ số với đúng bài toán3 lớp, ngân sách inner tuning bằng nhau và cùng thời điểm refit. Không dùng kết quả rủi ro nhị phân để thay thế đánh giá3 lớp.


## Đợt kiểm tra thông tin bổ sung đã chạy

Tất cả5 nhóm dùng cùng1.560 ngày/nhãn,3y,refit63 và15 trials cho mỗi outer fold với purged inner CV: tổng300 trials. Nhóm thiếu dữ liệu không được loại bớt ngày kiểm chứng; LightGBM xử lý NaN, không điền dữ liệu tranh chấp. VIX dùng ngày quan sát cộng2 ngày lịch, join backward có giới hạn7 ngày. Đối chứngcontrol khớp chính xác1.560/1.560 dự đoántrend cũ.

| Nhóm thông tin | Mean fold F1 | Worst fold F1 | Mean MCC |
|---|---:|---:|---:|
|control|0.3860|0.3728|0.1108|
|+OHLCV đồng thuận|0.3602|0.3241|0.0634|
|+VIX trễ|0.3491|0.2913|0.0532|
|+nhóm chỉ số|0.3397|0.3048|0.0288|
|+kết hợp tất cả|0.3490|0.3003|0.0550|

Không nhóm bổ sung nào được nhận là cải thiện. Kết quả không chứng minh những dữ liệu này luôn vô ích; chỉ cho thấy cấu hình và quy trình đã thử không vượt đối chứng. Báo cáo: `ml/reports/regime_information/20261018T153237_309880Z/`. `causal_audit.json` kiểm tra toàn bộ biên inner/refit, ngân sách tune và thời gian VIX. Bộ hồi quy cuối chạy148 kiểm thử, tất cả qua.

Bước tiếp theo đã chốt trong `next_family_plan.json`: thử SVC tuyến tính/RBF, CatBoost và ExtraTrees trên cùng19 feature gốc, cùng train-window/refit và ngân sách purged-inner. Chưa fit các model đó ở thời điểm tạo kế hoạch. Không sửa nhãn hay giảm coverage để làm đẹp F1. Mục tiêu vẫn chưa đạt; ứng viên development tốt nhất hiện tại vẫn là ensembletrend/risk khoảng0,3957 mean fold F1, chưa đủ bằng chứng cải thiện rõ.


## Đợt SVM/CatBoost/ExtraTrees đã chạy

Cùng19 featureclose/ETF/trend,3y,refit63,1.560 ngày kiểm chứng và15 trials mỗi họ ở mỗi outer fold: tổng180 trials. SVM dùng scaler chỉ fit trên inner/core train, không dùng PlattCV ngẫu nhiên (`probability=False`). CatBoost thử cảMultiClass vàMultiClassOneVsAll, không ghi file ngoài thư mục nghiên cứu. Kiểm tra360 biên inner và168 biênrefit của cả hai cách chọn tham số, tất cả nhãntrain đều kết thúc trước phiên dự đoán.

| Họ mô hình | F1 chọn tự do cân bằng/không | F1 chỉ chọn balanced | Worst F1 balanced | MCC balanced |
|---|---:|---:|---:|---:|
|SVC|0.3395|0.2919|0.2226|-0.0121|
|CatBoost|0.3579|0.3789|0.3524|0.1033|
|ExtraTrees|0.3147|0.3420|0.2788|0.0577|

Ởfold3, cả3 bản chọn tự do đều chọn cấu hình không cân bằng và dự đoán toàn bộ390 ngày làsideway:36 mẫu giảm và36 mẫu tăng đều bị bỏ sót. Bản balanced là phân tích phát sinh sau khi xem lỗi: chọn trialbalanced có điểm INNER cao nhất trong các trialđã lưu, không chạy thêmHPO, không chọn bằng điểmOUTER. Vì đã xem lỗi outer, đây vẫn là nghiên cứu DEVELOPMENT hậu kiểm, không phải xác nhận độc lập. Cân bằng có giúpCatBoost/ExtraTrees về điểm trung bình nhưng vẫn kém các đối chứng LightGBM cũ; SVC còn giảm điểm. Không nhận họ mới nào là cải thiện.

Artifacts: `ml/reports/regime_families/20261018T154106_332331Z/` và `ml/reports/regime_family_balance/20261018T154841_212343Z/`. Có dự đoán từng ngày, toàn bộtrial/inner score, tham số và các ma trận từngfold. `balance_sensitivity.csv` so sánh hai quy tắc chọn. Bộ hồi quy cuối159 kiểm thử đều qua; đây là kiểm tra pipeline, không phải bằng chứng chất lượng dự báo.

Bước nghiên cứu tiếp đã định nghĩa trong `next_return_distribution_plan.json`: học9 phân vị của lợi suất liên tục, sau đó quy phân phối dự báo về chính3 lớpT+20 ±5% cũ. So sánh raw/chuẩn hóa bằng sigma quá khứ,3y/expanding vàhai quy tắc chọn lớp cố định; không đổi nhãn đánh giá, không giảm coverage. Chưa train bước này tại thời điểm ghi báo cáo. Mục tiêu mô hình tốt vẫn chưa đạt.


## Phân phối lợi suất và ứng viên chọn expert nhân quả

Đã train4 bộ dự báo: raw/chuẩn hóa lợi suất log ×3y/expanding. Mỗi bộ dùng9 quantileGBM cố định, tổng1.008 head fits ở112 biên refit. Lợi suất dự báo được quy về đúng nhãn±5% cũ bằng quadrature9 điểm; không thay target. Có hai quy tắc chọn lớp định sẵn: argmax khối lượng lớp và argmax sau chia tần suất lớp của tậptrainđã đủnhãn. Nhãn/chuẩn hóa sigma được xây trên lịch VNINDEX đầy đủ trước khi lọc feature.

Bản expanding chuẩn hóa +chia prior đạt0,4151 mean fold F1 nhưng worst0,2736; Brier của khối lượng lớp cũng kém baseline tần suấttrain. Không nhận riêng bộ phân phối là model tốt hơn. Artifacts: `ml/reports/regime_return_distribution/20261018T155423_383833Z/`.

Sau đó thử hai phối hợp cố định và một bộ chọn có phản hồi trễ. Pool gồmensembletrend/risk cũ, từng classifiertrend/risk, trung bình4 bộ phân phối vàtrung bình2 bộ expanding. Các vector chỉ là điểm quyết định đã cân bằng lớp, không khẳng định xác suất được hiệu chỉnh.

Bộ chọn cập nhật mỗi20 phiên thị trường. Nó chỉ xem126 dự báo lịch sử có `label_end_date < selection_date`, đủ ít nhất5 mẫu mỗi lớp; chỉ đổi expert khi macroF1 lịch sử cao hơnensemble cũ ít nhất0,03. Nếu thiếu lịch sử hoặc không đủ chênh lệch thì dùngensemble cũ. Không lấy nhãn hiện tại/tương lai, không tối ưu trọng số. Quy tắc phát sinh từ kết quả đã xem, nên đây là DEVELOPMENT hậu kiểm, không phải test độc lập.

| Cách dự báo | Mean fold F1 | Worst fold F1 | Mean fold MCC |
|---|---:|---:|---:|
|ensembletrend/risk cũ|0.3957|0.3600|0.1437|
|phối hợp cố định với phân phối expanding|0.4376|0.3410|0.1794|
|bộ chọn chỉ dùng kết quả quá khứ|0.4205|0.3838|0.1412|

Bộ chọn qua point screen development so với cả đối chứngtrend vàrisk gốc (+0,02 meanF1, không giảm worstF1, tăng MCC, thắng ít nhất3/4 folds). Tuy vậy MCC trung bình chưa tăng so vớiensemble cũ và bootstrap block20/60 của chênh lệch F1 vớiensemble đều chứa0 (xấp xỉ[-0,009;0,058] và[-0,010;0,057]). Chưa xác nhận ưu thế thật. Không dùng điểm0,4376 cao hơn của phối hợp cố định để che worst fold thấp.

Kiểm chứng thêm: mô phỏng mặc định khớp1.560/1.560 dự đoán sau khi thêm giao diện audit;5 prefix ngày khác nhau vẫn khớp khi cố tình bỏ/đổi nhãn chưa trưởng thành;80 biên chọn đều dùng nhãn kết thúc trước ngày chọn. Tám nhiễu một tham số cho meanF1 khoảng0,4173–0,4256, nhưng worstF1 còn nhạy với cửa sổ dài (xuống0,3446). Giữ nguyên rule126/5/0,03/20, không chọn lại cấu hình đẹp hơn trong bảng sensitivity.

Ứng viên nghiên cứu đã khóa: `ml/artifacts/regime_multiclass_candidate_20261018/contract.json`. Có `historical_replay_manifest.json` lưu tham số/anchor các fold cũ cho kiểm chứng bộ suy luận. Chưa có runtime native mới, xác suất hiệu chỉnh hoặc bằng chứng độc lập; không thay modelbackend và chưa hoàn thành mục tiêu chất lượng. Bước tiếp theo là tái lập inference độc lập rồi thu dự báo mới theo đúng contract.

Báo cáo: `ml/reports/regime_expert_selection/20261018T160007_360834Z/`; xem `model_comparison.png`, `robustness_report.json`, `paired_intervals.json`, `parameter_sensitivity.csv`. Bộ hồi quy cuối171 kiểm thử đều qua; không dùng kiểm thử phần mềm thay bằng chứng chất lượng dự báo.


## Bộ suy luận native độc lập đã tái lập

`ml/regime_multiclass_native.py` tự xây nhãn/partition, fit từ tham số đã khóa, lưu/nạp nativeBooster, tính lại quadrature và tự tínhF1/chọnexpert mà không gọi hàm train/predict/selector của script thí nghiệm. Dùng chung các helper tạo feature đã pin để giữ đúngschema. Tất cả1064 booster ở28 gói lịch sử đã lưu và kiểm tra hash; đây là38 model mỗi lần refit, không phải1064 cấu hình HPO mới.

Kết quả tái lập: đúng1560/1560 quyết định củaứngviên, cả5 expert đều đúng1560/1560 nhãn và80/80 lần chọn có cùng tênexpert. Sai số score lớn nhất2,22e-16. Native save/reload được so từng expert/head với wrapper trước khi chấp nhậnbundle. Mỗi bundle cóidentity của contract, code, prefixtrain và tham số; hash metadata và model file được kiểm tra khi nạp.

Báo cáo: `ml/reports/regime_multiclass_native/20261018T162002_744919Z/parity_report.json`. Nativeweights và khóa nằm ở `ml/artifacts/regime_multiclass_candidate_20261018/native_bundles/` và `native_runtime_lock.json`. Tái lập lịch sử khi cần:

```bash
python3 ml/regime_multiclass_native.py
```

Đã xuất1560 dòng native OOFscores ở `ml/reports/regime_native_scores/20261018T162849_386798Z/`. `decision_score_*` là score đã cân bằng để chọn lớp; `component_mass_*` là hiệu chỉnhprior xấp xỉ/rawquantilemass. Cả hai chưa được khẳng định là xác suất được hiệu chỉnh. Dữ liệu là chạy lại quá khứ, không phải dự báo prospective. Cómanifest pinhash và điều kiện chỉ dùng nhãn kết thúc trước ngàyrefit của các bộ hiệu chỉnh sau này.

Bộ hồi quy cuối180 kiểm thử đều qua. Điều này xác nhận phần mềm tái lập, không giải quyết độ bất định của lợi thếdự báo. Chưa có pipeline phát dự báo3 lớp cho ngày mới hay thaymodelbackend. `probability_evaluation_plan.json` đã chốt trước khi kiểm tra độ tin cậy: multinomiallogisticC0,1, train trên504 OOFmatured gần nhất, tối thiểu252 và10 mẫu/lớp, refit20 phiên; baseline là tần suất lớp504 phiên quá khứ đầyđủ vớiLaplace1. Báo cáo riêngBrier/logloss, coverage vàF1argmaxxácsuất so với quyết định đã khóa; không thayđổi rule0,420 để làm đẹp kết quả.


## Nhãn động và các mô hình phối hợp — 19/10/2026

Đã chạy đối chứng ±5% và nhãn ±1 sigma trên cùng 1.560 phiên, huấn luyện lại hai classifier; giữ nguyên tham số, không dò ngưỡng. Báo cáo đầy đủ: `ml/reports/regime_dynamic_experts/20261019T033757_910222Z/README.md`.

Trong bài toán nhãn động, equal LightGBM đạt mean/worst F1 0,4488/0,3908; blend 50/50 với hai phân phối expanding đạt 0,4893/0,4000; selector đạt 0,4789/0,3721. Không so F1 trực tiếp với bài toán ±5%. Khoảng bootstrap 60 phiên của blend trừ equal vẫn chứa 0; chưa chấp nhận triển khai. Ngưỡng tăng trung vị 4,61%, dưới 5% ở 55,45% phiên. Giữ nguyên contract/model đã khóa.


## Tinh chỉnh riêng nhãn động — 19/10/2026

Đã chạy 24 trial × 3 inner fold đã purge cho mỗi nhóm trend/risk và mỗi outer fold, tổng 192 trial. Hai quy tắc chọn theo độ bền và macro F1 trên cùng pool trial đều không vượt blend cũ: mean/worst F1 0,4775/0,3619 và 0,4830/0,3714 so với 0,4893/0,4000. F1 lớp giảm và tăng đều thấp hơn đối chứng. Giữ đối chứng, không thay model ứng dụng. Báo cáo và phân tích lỗi theo fold/năm/biến động: `ml/reports/regime_dynamic_tuning/20261019T042757_126390Z/README.md`. Không kết luận từ điểm inner tăng rằng outer sẽ tốt hơn.


## Bốn nhánh cải thiện tăng/giảm — 19/10/2026

Đã chạy specialist chọn bằng inner fold, đặc trưng mới cho hồi quy phân vị, adapter dùng nhãn quá khứ đã mature, và CatBoost MultiQuantile học chung chín phân vị. Không nhánh chính nào vượt đối chứng theo tiêu chí định trước. Mean/worst F1 lần lượt 0,4510/0,3716; 0,4886/0,4024; 0,4719/0,3780; 0,4785/0,3956 so với 0,4893/0,4000. Giữ đối chứng nghiên cứu, không thay model ứng dụng. Tổng hợp: `ml/reports/regime_research/directional_followup_20261019.md`. Bộ 178 kiểm thử hồi quy và hai kiểm thử backend CatBoost mới đều qua. Mục tiêu mô hình tốt hơn chưa đạt.


## Mở rộng tìm kiếm nhãn động — 19/10/2026

Đã hoàn tất 7 quy trình: thông tin OHLCV/VIX/indices, lịch sử dài và transfer chuẩn hóa biến động, 8 họ model mới, focal/label smoothing, CDF/19 quantile, chọn inner macro thuần và chọn F1 bản trộn hoàn chỉnh. Cao nhất quan sát được là bộ chọn thông tin bằng inner fold: mean/worst F1 0,4925/0,4000 so với 0,4893/0,4000. F1 giảm 0,2905 thấp hơn đối chứng 0,2946; khoảng bootstrap60 của mức tăng meanF1 [-0,01347;0,02307] chứa0. Chưa ứng viên nào qua tiêu chí nâng cấp. Giữ benchmark, lưu challenger; không thay ứng dụng. Tổng hợp: `ml/reports/regime_research/broad_search_20261019/README.md`. 190 kiểm thử đều qua.


## Goal F1 đang hoạt động: vòng1 — 19/10/2026

Thử cadence20/5,5seed,decay126/252,calendar và lọc score nhân quả. F1 cao nhất quan sát0,494927 so với0,492508 trước đó; worst0,400628; bear0,302320; bull0,436668. Kiểm tra độc lập lại toàn bộ nhãn/endpoints từrawClose và1560dự đoán đều khớp. Mức tăng nhỏ, khoảng bất định chứa0; chưa đạt mục tiêu tốt hơn rõ ràng. Goal vẫn active, không thay ứng dụng. Tổng hợp `ml/reports/regime_research/f1_goal_20261019_stage1/README.md`.


## Goal F1 đang hoạt động: vòng2 — 19/10/2026

Thử hysteresis, lọc Markov tiến nhân quả, chỉnh tỷ trọng/nhiệt độ bằng OOF mature, GRU1/10 và gate chọn component. Điểm cao nhất mới0,497292; worst0,397404; bear0,323324; bull0,424419. Tradeoff và khoảng bất định chưa cho phép chấp nhận cải thiện. Goal active. 201 kiểm thử +1 test gate mới qua,168 checkpoint GRU save/reload sai số0. Tổng hợp `ml/reports/regime_research/f1_goal_20261019_stage2/README.md`.


## Goal F1 đang hoạt động: vòng3 — 19/10/2026

Matched-cadence inner calibration robust diagnostic đạt50,85%; empirical RandomForest return density trộn với ensemble quantile đạt51,2149% meanF1, worst39,1120%, bear31,6467%, bull47,8422%, MCC0,2959. So với dynamic blend ban đầu48,9309%, tăng2,2840 điểm nhưng worst giảm0,8893 điểm. Không đổi nhãn/cohort hay ứng dụng. 234 tests qua;23 forecastfiles và34 sourcehashes được audit độc lập; inner hệ số tái lập4/4 folds. Goal active, chưa independent acceptance; xem `ml/reports/regime_research/f1_goal_20261019_stage3/README.md`.


## Goal F1 đang hoạt động: vòng4 — 19/10/2026

Matched inner forest fusion không cải thiện (robust47,71%,macro49,53%). Forest học đồng thời return/absolute return giúp mốc cao nhất51,3398%, worst39,2464%, bear32,2930%,bull47,3608%; +0,1249điểm so với51,2149% và khoảng bất định chứa0. Soft-margin shrink50,5816% không dùng; đã sửa công thức interval logistic tránh triệt tiêu số học,2regressiontests qua. Audit độc lập10scorefiles,49hashes,4×225innerchoices và10outerpipelines khớp scoremaxerror3,33e-16. Bảy test trọng tâm qua. Goal active, không thayapp. Xem `ml/reports/regime_research/f1_goal_20261019_stage4/README.md`.


## Goal F1 đang hoạt động: vòng5 — 19/10/2026

Forest thêm thông tin không cải thiện (48,69–50,01%). Analog density đạt51,4488% mean/worst39,3661%; shock forest shrink đạt51,3745% mean/worst40,3056%, MCC0,3005. Shock thắng4/4fold so với mốc đầu goal49,2508% và tăng cả worst/bear/bull/MCC; tuy nhiên block20 CI[-0,000257;0,038300] vẫn chứa0. Giữ cả hai ứng viên nghiên cứu, chưa chấp nhận triển khai. 23test trọng tâm qua;10forecastfiles,49sourcehashes,448fit boundaries và10scorepipelines audit độc lập khớp (maxerror2,22e-16). Goal active; xem `ml/reports/regime_research/f1_goal_20261019_stage5/README.md`.


## Goal F1 đang hoạt động: vòng6 — 19/10/2026

Mahalanobis/nonoverlapping analog không cải thiện (primary50,47–50,82%). Forest thêm lịch sử2010/ETF missing đạt tối đa51,1308%; volume precision budget0,01% đạt51,2914%, dù độ phủ field56,79→73,91%. Không sửa rawdata hoặc benchmark. Giữ51,4488% highestmean và shock51,3745%/worst40,3056%. Tám test trọng tâm qua; audit13forecastfiles,47hashes,560fit records,13outerpipeline scores,12neighborhood checks,112extendedcohorts và4.174volume rows khớp. Goal active; xem `ml/reports/regime_research/f1_goal_20261019_stage6/README.md`.


### Stage7: full native shock model and independent parity audit

Exported the complete shock_shrink ensemble and empirical populations:2LightGBM classifiers,90quantile boosters,8forests, leaf return samples and compact/full analog stores. Full historical replay retrains/reloads28bundles across1560dates; all decisions match and independently recomputed mean macroF1 remains0.5137451636929175, worst0.403056383096105. Checksum verification covers2828native payloads and84training-cohort timing receipts. A latest-reviewed snapshot at2026-10-01 retains current unlabelled feature rows; its feature builder matches archived features exactly. No live replacement.

New matched/extended close-only analog tests give0.5114275/0.5143056; auxiliary future-path-supervised forest gives0.5111907. None beats the existing0.5144884 high-mean candidate. A fixed causal logistic probability diagnostic worsens aggregate Brier/log loss versus raw shock decision scores; both remain weaker than mature class-frequency prior in fold3. No calibration acceptance. Freshness, before-refit and expired-bundle guards checked;5new unit tests pass. Research snapshots are not independent prospective predictions.

Detailed report:ml/reports/regime_research/f1_goal_20261019_stage7/README.md. Artifact:ml/artifacts/regime_shock_candidate_20261019T090555_259289Z. Need fresh source data, fixed serving refit policy and prospective forecast ledger before product readiness claims.
