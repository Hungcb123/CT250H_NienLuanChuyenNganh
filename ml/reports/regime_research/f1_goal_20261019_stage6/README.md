# Nghiên cứu F1, vòng 6 — 19/10/2026

Vòng này hoàn tất ba thử nghiệm và một audit nguồn volume. **Chưa có bản mới vượt 51,4488% mean fold macro F1**. Giữ hai ứng viên nghiên cứu: analog-shrink51,4488% / worst39,3661% và shock-shrink51,3745% / worst40,3056%. Goal vẫn active; không thay model ứng dụng.

Tất cả điểm dưới đây dùng cùng1.560 ngày T+20, bốn fold390 ngày và nhãn ±1sigma. Không đổi ngưỡng, bỏ ngày đánh giá hoặc dùng F1 pooled thay cho trung bình fold. F1 không phải accuracy.

| Phương án | Mean F1 | Worst F1 | Bear F1 | Bull F1 | Mean MCC |
|---|---:|---:|---:|---:|---:|
| Đối chứng analog-shrink |51,45%|39,37%|32,02%|47,99%|0,2978|
| Mahalanobis, thay nửa analog |50,82%|39,23%|30,64%|47,66%|0,2917|
| Tách20phiên, thay nửa analog |50,47%|39,23%|30,20%|47,16%|0,2877|
| Cả hai, thay nửa analog |50,70%|38,89%|30,78%|47,21%|0,2889|
| Thêm lịch sử, thay nửa forest |50,90%|39,21%|29,76%|48,48%|0,2983|
| Thêm lịch sử, thay toàn bộ forest |51,13%|40,19%|31,26%|47,88%|0,2978|
| Volume với budget0,01%, thay nửa forest |51,29%|39,37%|31,87%|47,72%|0,2952|
| Volume với budget0,01%, thay toàn bộ forest |51,29%|39,37%|31,87%|47,72%|0,2952|

Ba diagnostic thay toàn bộ analog đạt50,49%,49,75%,49,92%, cũng không cải thiện. Hai công thức volume có score khác nhau nhưng cùng nhãnargmax trên tập đánh giá, nên các metrics bằng nhau; không phải bỏ sót một lần fit. Không đổi tỷ trọng sau khi xem kết quả để tìm điểm đẹp hơn.

## Khoảng cách và độ chồng lấn analog

Mahalanobis dùng median/IQR và covarianceLedoitWolf chỉ fit trên train đã có kết quả. Thêm ridge cố định1e-8×max(trace/d,1), truyền inverse covariance tường minh vàoSciPy; không dùng mặc định có thể fit cả validation. Hai feature views, raw/normalized returns, k tối đa100, Gaussian bandwidth và cách cân bằng prior giữ nguyên.

Nhánh tách thời gian duyệt stable distance order, chọn phiên gần nhất còn hợp lệ rồi loại các origin cách nó dưới20 phiên trên **lịch VNINDEX đầy đủ**. Nó chọn thực tế28–96 analog thay vì luôn100; minimum calendar separation đúng20. Nhãn của các origin được chọn không chồng cửa sổ T+20, nhưng điều đó không chứng minh các quan sát độc lập thống kê. Nhánh này mất F1; không đánh đồng quy tắc có vẻ hợp lý với chất lượng dự báo thực tế.

Các ứng viên chính thay nửa thành phần analog25%: density=.75basic+.125analog cũ+.125analog mới. Diagnostic thay toàn bộ phần analog25%. Các phần quantile/forest/classifier/inner anchor/current-EMA5 giữ nguyên; không có outer metric selection.

## Học thêm lịch sử mà không tạo ETF giả

`extended_feature_history` dựng endpoint và nhãn trên lịch VNINDEX đầy đủ trước khi lọc warmup. Giữ các hàng có đủ core close/trend, sigma và label; cho phép bốn ETF features làNaN trước khi có dữ liệu hoặc tại lỗ hổng. Không bfill/ffill giá hay feature. Native RF xử lý missing branches.

Eligible history tăng từ **2.341 lên3.955 hàng**, earliest từ2016-02-25 về2010-10-22. Các ngày gốc có toàn bộ19feature và target/sigma khớp đến1e-12; sai số feature thực tế0. Thêm cả các ngày ETF bị thiếu trong giai đoạn sau, không chỉ phần lịch sử trước2016. Hai ETF dates ngoài lịch đã được review trước đây (2018-01-23/24) chỉ bị loại trong bộ nhớ, rawfiles giữ nguyên; ngày lạ khác sẽ báo lỗi.

Train expanding, cùng28biên refit63phiên và bốn forest heads mean/magnitude×raw/normalized, tham số không đổi. Chỉ thay nửa hoặc toàn bộ phần forest37,5% trong density hiện tại; giữ quantile37,5% và analog25%. Nhánh replace có worst40,19% nhưng thấp hơn cả mean và worst của ứng viên shock-shrink đã có, nên không thay benchmark.

## Volume: kiểm tra nguồn trước khi thay feature

Audit chỉ dùng các bar có close khớp giá đã review và OHLC bounds hợp lệ. Với KBS/VND,95,67% overlap có sai khác volume dưới1%,78,90% dưới0,01%; quy tắc cũ dùng tolerance tuyệt đối1share. Các tỷ lệ này mô tả nguồn, không chứng nhận hai broker dùng cùng định nghĩa volume.

Trong các mẫu đủ điều kiện, không thấy dấu hiệu volume lệch đơn vị theo hệ số10/100/1000; tương quan thay đổi logvolume cao nhất ở lag0 cho cả ba cặp (0,9913;0,9676;0,9784). Vì thế không tự nhân/chia đơn vị hoặc dịch ngày để ép khớp. Xem `volume_alignment_audit.json`, `volume_ratio_audit.csv`, `volume_lag_audit.csv`.

Thử một **measurement budget cố định0,01%**, chọn trước khi chấm model: cần một nhóm lớn nhất duy nhất gồm ít nhất hai broker có range≤max(1share,0,0001×groupmax). Reject chain mơ hồ, nguồn đơn lẻ, giá trị không dương và bất đồng lớn hơn. Vẫn dùng cùng điều kiện close/OHLC để xét nguồn. Không thay sổ absolute-consensus cũ hoặc giá chứng khoán nào.

Từ sổ volume mới tính thêm hai feature nhân quả: logvolume/median60(min30 quan sát) và logvolume/volume.shift5 trên lịch đầy đủ. Không điền lỗ hổng. Độ phủ field trên1.560 ngày tăng **56,79%→73,91%**; hai feature đạt71,86% và71,67%. Độ phủ tốt hơn chưa chuyển thành F1 cao hơn: cả hai công thức đạt51,2914%, thấp hơn51,4488%.

Đây là một giả thuyết về precision của số đo, không phải tuyên bố đã sửa volume thành dữ liệu sàn chuẩn hoặc xác minh được historical vintage. Giữ dữ liệu nguồn và model ứng dụng cũ.

## Kiểm chứng

Tám kiểm thử trọng tâm đều qua; sáu test mới bao gồm covariance không phụ thuộc query/target, separation theo lịch thực tế, zero-distance/zero-IQR, ETF trước ngày có dữ liệu vẫnNaN, endpoint không nén lịch, feature future-prefix invariance và consensus không chấp nhận chain mơ hồ.

Audit độc lập xác nhận:

- Raw-price labels/endpoints,1.560ngày×4fold và metrics của13forecastfiles.
- 47sourcehashes và560fit records có target endpoint trước prediction boundary.
- Tái lập13pipeline phối hợp/EMA bằng công thức riêng; max score error2,22e-16.
- Tái lập12metric/feature/target combinations ở block đầu63phiên bằng NumPy distances và greedy lựa chọn khác triển khai; max error6,11e-16.
- Tự dựng lại eligible history từraw-calendar labels và đếm lại112refit cohorts, kể cả số hàng thiếuETF.
- Tự dựng lại toàn bộ4.174ngày volume consensus, voters, rolling/lag features từ ba rawbroker snapshots, không gọi helper consensus mới.

Xem `independent_metric_audit.json`. Audit triển khai độc lập vẫn dùng cùng lịch sử, không tạo independent test hoặc chứng minh lợi thế tương lai. Chưa có native inference bundle mới hay deployment acceptance.

Chạy lại khi cần:

```bash
python3 ml/experiment_regime_metric_analog.py
python3 ml/experiment_regime_extended_forest.py
python3 ml/experiment_regime_relative_volume.py
python3 ml/reports/regime_research/f1_goal_20261019_stage6/recalculate.py
```

Reports:

- `ml/reports/regime_metric_analog/20261019T073046_885436Z/`
- `ml/reports/regime_extended_forest/20261019T073305_918472Z/`
- `ml/reports/regime_relative_volume/20261019T083345_837476Z/`

Bước tiếp theo: kiểm tra thêm lịch sử cho **analog có điều kiện theo trạng thái giá**, thay vì cho forest toàn cục. Có đối chứng close-only trên ngày train cũ để tách hiệu ứng bỏ ETF feature khỏi hiệu ứng thêm dữ liệu; không dùng khoảng cách với NaN hoặc tạo giá ETF trước khi tồn tại. Chốt feature views/k/tỷ trọng trước khi chấm outer.
