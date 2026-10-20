# Tổng quan VNxCapital

Bản thử giao diện ngày 20/10/2026, áp dụng riêng tab Tổng quan.

- Ưu tiên: tổng tài sản, hiệu suất, phân bổ, tài sản đang giữ, việc cần xử lý.
- Tổng tài sản là số chính; lãi/lỗ, tiền khả dụng và tiết kiệm dùng một dải thông tin, không tách thành bốn card.
- Phân bổ dùng thanh ngang trung tính, có vạch mục tiêu SAA và số thực tế/mục tiêu hiển thị cùng nhau.
- “Cần chú ý” không lặp nhiều thông báo cân bằng; nút xem kế hoạch chỉ hiện khi có đề xuất. Giao dịch vẫn cần luồng xác nhận hiện có.
- Biểu đồ ghi rõ Danh mục và VN-Index; giữ các khung thời gian, chế độ so sánh và NAV.
- Nền và đường phân cách tạo nhóm; giảm khung, icon trang trí và chữ in hoa. Xanh/đỏ dành cho biến động và thao tác giao dịch.
- Màn hình nhỏ xếp các vùng thành một cột; bảng tài sản cuộn ngang trong vùng bảng.

Các tab khác và lớp tính toán giữ nguyên trong lần thử này.

## Áp dụng toàn bộ workspace

Cùng phong cách được áp dụng cho Thị trường, Sổ giao dịch, Tối ưu danh mục
(kể cả phân tích dữ liệu thực), Tín hiệu thị trường, Tiết kiệm, Khảo sát và Cố vấn.
Các lớp `vnx-panel`, `vnx-stat-strip`, `vnx-stat`, `vnx-detail` trong `index.css`
định nghĩa vùng nội dung phẳng, dải chỉ số và chi tiết có đường phân cách.
Điều khiển chọn, trạng thái cảnh báo, hộp thoại và bước xác nhận vẫn giữ dấu hiệu tương tác.
Không thay đổi cách tính toán, payload API hoặc cơ chế thực hiện giao dịch.
