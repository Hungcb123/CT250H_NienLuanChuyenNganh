# Bộ chạy ứng viên nghiên cứu đã đóng băng

Ứng viên `equal_standardized_3y_expanding_online120_v1` chưa được chấp nhận triển khai. Trên development, nó bắt56 mẫu giảm >5%, cảnh báo sai169, so với55 và270 ở model volatility trước. Precision24,89%, recall29,32%, cảnh báo14,42%; còn trượt một số tiêu chí và khoảng bootstrap chứa0. Không coi đó là bằng chứng thắng trên test độc lập.

## Artifacts hiện hành

`ml/artifacts/regime_shadow_candidate_20261017_v2/` chứa:

- `contract.json`: định nghĩa feature/nhãn, tham số cây, các cửa sổ và hash code nghiên cứu đã đóng băng. Nội dung hợp đồng giữ nguyên từ bản đầu.
- `runtime_lock.json`: hash bộ chạy, các dependency nguồn, thời điểm khóa bộ chạy và hash báo cáo tái lập.
- `environment_lock.json`: phiên bản Python/numpy/pandas/scipy/LightGBM/sklearn để bộ chạy theo lịch kiểm tra.
- `bundles/`: model LightGBM native `.txt`, hash, thứ tự feature/classes và thông tin core/calibration của từng lần refit. Không thay ONNX backend.
- `readiness.json`: trạng thái sẵn sàng, số dự báo prospective thực sự và kết quả chặn phát dự báo cho ngày cũ.

Bản đầu được giữ nguyên kèm `superseded.json`, thay thế trước khi có bất kỳ dự báo prospective nào. Bản2 sửa khởi tạo ngưỡng khi chạy một ngày nằm sau archive: phải dựng đủ các điểm trung gian, không được bỏ qua lịch sử chỉ vì lệnh chạy có `--start` muộn.

## Kiểm chứng đã chạy

Bộ chạy độc lập khớp toàn390 ngày của fold cuối (2025-02-10 đến2026-09-03), cả tín hiệu, score và threshold; sai số số học lớn nhất khoảng9e-16. Native model lưu/đọc lại được kiểm tra xác suất trước khi chấp nhận bundle. Báo cáo: `ml/reports/regime_shadow/parity_runtime_v2_20261017/parity_report.json`.

Snapshot mới `ml/data/research/regime_shadow/20261017T164231_009575Z/` có thêm11 phiên đến16/10/2026. Giá đóng cửa mới được đối chiếu VCI/VNDirect. Prefix đã duyệt được giữ nguyên; snapshot sau tiếp tục bảo toàn mọi giá đã nhận ở snapshot trước. Bất đồng ngày/giá hoặc sửa giá lịch sử làm snapshot bị cách ly. Khi nạp dữ liệu, bộ chạy kiểm tra lại hash manifest, dữ liệu và raw response, rồi đối chiếu Close nguồn.

`ml/reports/regime_shadow/latest_seed_runtime_v2_20261017/` chứa31 ngày chạy lại quá khứ từ04/09 đến16/10 để khởi tạo trạng thái. Tất cả đều mang nhãn `research_backcast`; không tính thành dự báo phát đúng thời điểm. Giá đã đọc đến16/10 cũng được ghi vào registry exposure để không tái dùng như test chưa xem.

## Lệnh vận hành

Tải snapshot mới, không ghi đè snapshot cũ:

```bash
python3 ml/collect_regime_shadow_data.py
```

Phát dự báo sau khi có Close của đúng ngày hiện tại, sau15:05 giờ Việt Nam:

```bash
python3 ml/regime_shadow.py --data <snapshot_mới>/VNINDEX.csv --emit
```

Lệnh phát dự báo từ chối ngày cũ, cuối tuần, trước giờ đóng cửa và code/data bị thay đổi. Dự báo được ghi vào `prospective_predictions.jsonl` bằng hash chain và khóa file; cùng candidate/ngày không bị ghi đè. Timestamp là xác nhận từ đồng hồ máy, không phải công chứng độc lập. Trạng thái lịch sử dùng để khởi tạo được ghi rõ và không được tính vào hiệu quả prospective.

Dự báo lưu cả quyết định của expert3 năm và expanding làm đối chứng, cùng model version, feature hash, snapshot hash và Close tại thời điểm phát. Score là điểm xếp hạng, không phải xác suất sự kiện đã được calibration.

Chạy lại một khoảng quá khứ để kiểm tra bộ chạy:

```bash
python3 ml/regime_shadow.py --start 2025-02-10 --end 2026-09-03 \
  --output-dir <thư_mục_mới> --verify-parity
```

Bộ chạy tự dựng những điểm lịch sử trung gian còn thiếu kể từ archive. Khoảng trả về chỉ gồm các ngày yêu cầu; ngưỡng không phụ thuộc việc chọn ngày bắt đầu muộn hay sớm.

Chưa có dự báo prospective nào ở thời điểm tạo readiness. Cần phiên mới sau khi khóa bộ chạy và sau đó20 phiên giao dịch để biết nhãn T+20 đầu tiên. Đủ nhãn không đồng nghĩa đủ biến cố độc lập: kết quả sẽ cần kiểm tra độ bất định và tính ổn định trước khi kết luận model tốt.

## Lịch chạy và chấm tự động

Ngày18/10/2026 đã cài một tác vụ trong crontab của người dùng, kiểm tra mỗi15 phút. Chỉ sau15:05 giờ Việt Nam vào ngày trong tuần, bộ chạy mới lấy dữ liệu và phát dự báo cho đúng phiên hiện tại. Cuối tuần, trước giờ đóng cửa, thiếu dữ liệu hoặc dữ liệu không khớp đều không phát dự báo. Chạy thành công một phiên không tạo lại dự báo khi cron gọi tiếp. Máy/WSL và dịch vụ cron phải đang chạy; các phiên bị bỏ lỡ không được điền lại thành dự báo prospective.

`operations_lock.json` khóa code vận hành, bộ chấm, môi trường và `prospective_protocol.json`. `schedule_receipt.json` lưu lệnh đã cài và vị trí bản sao crontab cũ. Các tác vụ khác được giữ nguyên. Dự báo và kết quả thực tế nằm trong hai ledger riêng; bộ chấm chỉ ghi nhãn sau đúng20 phiên trên lịch dữ liệu đã được duyệt, không dùng20 ngày lịch. Return đúng−5% không được tính là sự kiện giảm hơn5%.

Quy tắc đánh giá đã khóa trước dự báo đầu tiên: tối thiểu240 phiên đã có kết quả,20 mẫu giảm hơn5% và3 cụm khoảng nhãn dương không giao nhau; precision ít nhất25%, recall ít nhất30%, tỷ lệ cảnh báo không quá15%. So sánh với expert3 năm đã phát cùng thời điểm bằng bootstrap block20 và60 phiên: cận dưới95% của chênh lệch precision phải lớn hơn0, của recall phải lớn hơn−5 điểm phần trăm. Đây là điều kiện xem xét tiếp, không tự động triển khai hay chứng minh có lợi nhuận. Các cụm không giao nhau cũng không đảm bảo độc lập kinh tế.

Xem trạng thái thực tế:

```bash
python3 ml/run_regime_shadow_daily.py --status
```

Chạy một lượt ngay (vẫn giữ mọi điều kiện thời gian/dữ liệu):

```bash
python3 ml/run_regime_shadow_daily.py
```

Xem kết quả chấm ở `ml/artifacts/regime_shadow_candidate_20261017_v2/prospective_status.json`, trạng thái lượt chạy ở `daily_state.json`, log cron ở `daily.log`. Bộ chạy chỉ ghi file nghiên cứu cục bộ; không gửi thông báo. Nếu sửa code hoặc cập nhật phiên bản thư viện đã khóa, bộ chạy sẽ từ chối chạy và cần một quy trình phiên bản mới được kiểm chứng lại.
