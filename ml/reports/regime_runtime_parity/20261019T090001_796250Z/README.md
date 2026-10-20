# shock_shrink: bước đầu chuẩn bị suy luận độc lập

Đã tách phần kết hợp score khỏi mã thí nghiệm. Module `ml/regime_shock_score_runtime.py` nhận sáu vector score thành phần; không nhận nhãn, lợi suất tương lai hoặc đọc báo cáo. Công thức kết hợp và EMA5 giữ nguyên bản nghiên cứu. Đầu ra ghi rõ score không phải xác suất đã hiệu chỉnh; trường `calibrated_probability` là null.

Kiểm tra replay toàn bộ 1.560 phiên, lưu/nạp JSON trạng thái sau từng phiên:

- 1.560/1.560 nhãn dự đoán khớp bản lưu.
- Sai số score lớn nhất 2,220446049250313e-16.
- Macro F1 trung bình bốn fold giữ nguyên 51,3745%; fold kém nhất 40,3056%.
- 87 file nguồn được kiểm tra, gồm các source receipt bắc cầu trong plan.
- Hai test kiểm tra độc lập công thức, restart, cuối tuần, phiên bị bỏ lỡ, đầu vào lỗi, phiên trùng và trạng thái sai phiên bản đều đạt.

Module yêu cầu ngày phiên liền trước do lịch thị trường cung cấp. EMA tiếp tục qua cuối tuần khi hai ngày là hai phiên liên tiếp; reset khi thiếu dự báo của một phiên giao dịch. Lỗi đầu vào không làm trạng thái tiến lên. Mỗi stream_id cần gắn với phiên bản model và tài sản.

File `historical_component_fixture.npz` chỉ chứa các score thành phần, ngày và tham số kết hợp đã chọn cho từng giai đoạn lịch sử. Đây là fixture replay; không chứa bộ trọng số đủ để dự đoán từ dữ liệu thị trường mới. File này không phải bộ model triển khai. `recipe.json` khóa công thức kết hợp; `sources.json` và `checksums.json` lưu dấu vết nguồn/đầu ra. Không tự suy ra quy tắc chọn tham số cho tương lai từ tham số từng fold.

Chưa hoàn thành: xuất/nạp model LightGBM, lưu các forest cùng mẫu lợi suất trong lá, lưu kho analog và bộ chuẩn hóa, dựng đặc trưng đúng hợp đồng, chốt quy tắc chọn tham số chỉ dùng dữ liệu đã trưởng thành. Sau đó phải kiểm tra parity từ dữ liệu thị trường đến score, và đánh giá xác suất riêng trước khi giao diện hiển thị độ tin cậy. Chưa thay model của web, chưa có đánh giá độc lập hay chấp nhận triển khai.

Chạy lại:

```bash
python3 -m unittest discover -s ml -p test_regime_shock_score_runtime.py -v
python3 ml/freeze_regime_shock_runtime.py
```

Mỗi lần replay tạo thư mục báo cáo mới; không ghi đè báo cáo này.
