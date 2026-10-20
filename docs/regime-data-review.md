# Điều tra dữ liệu regime — 17/10/2026

Lần chạy `ml/reports/regime_v2/20261017T125935_040656Z` đã hoàn tất, nhưng holdout
còn yếu: T+20 XGBoost Macro F1 0.311/MCC 0.019; T+60 CatBoost F1 0.239/MCC
−0.055; T+120 LogisticRegression F1 0.280/MCC −0.104. Chưa kết luận được nguyên
nhân chính; các điểm dưới đây phân biệt kiểm chứng dữ liệu với hiệu quả mô hình.

## Kết quả đối chiếu bộ cũ

Toàn bộ **1.430 Close VNINDEX** từ 04/01/2021 đến 01/10/2026 khớp các phản hồi
Vietcap, KBS và VNDIRECT đã tải ngày 17/10/2026. OHLC và volume không hoàn toàn
khớp giữa nguồn; hiện pipeline close-only không dùng các cột đó làm feature.
Đây là kiểm chứng theo các feed broker, không phải chứng nhận độc lập của HOSE.

ETF cũ có 724 dòng, 210 dòng volume bằng 0. Trên 685 ngày cùng có trong dữ liệu
Vietcap tải mới, **271 giá Close khác nhau**, trong đó 103 dòng ETF cũ có volume
dương. Không thể coi đó chỉ là vấn đề phiên nghỉ hoặc tự sửa bằng điền giá.
Bộ cũ được giữ nguyên để đối chiếu, không đưa vào phép so sánh mới.

## Bộ nghiên cứu mới

Thư mục: `ml/data/research/brokers_2010_20261001_reviewed/`.

| Nội dung | Kết quả |
|---|---:|
| VNINDEX nguồn Vietcap trước review | 4.176 dòng |
| VNINDEX canonical sau review | **4.174 phiên** |
| Khoảng VNINDEX | 04/01/2010–01/10/2026 |
| Close đổi so với Vietcap | 7 ngày, có quyết định nguồn từng ngày |
| Ngày HOSE ngừng giao dịch bị loại | 23–24/01/2018 |
| Phiên chỉ có một nguồn đối chiếu hiện tại | 598 phiên trước 01/06/2012 |
| ETF Vietcap tải mới | 2.676 dòng từ 07/01/2016 |
| ETF canonical | **2.675 dòng**, loại xung đột 14/03/2019 |

KBS cung cấp VNINDEX từ 01/06/2012, VNDIRECT từ 24/08/2017 trong các request đã
lưu. Không gán nhãn rằng toàn bộ lịch sử 2010 đều được hai nguồn xác nhận.

Các quyết định Close dùng đồng thuận ít nhất hai broker khi có ba giá; không
lấy trung bình. Hai điểm bất đồng chỉ có hai nguồn được đối chiếu báo cáo MBS:
[19/06/2015: 584,70](https://www.mbs.com.vn/media/dkrdomtr/t-e1-bb-95ngh-e1-bb-a3pth-e1-bb-9dng_19062015.pdf),
[02/10/2015: 562,31](https://www.mbs.com.vn/media/kjqdggnz/t-e1-bb-95ngh-e1-bb-a3pth-e1-bb-9dng_02102015.pdf).
Nguồn đúng không cố định: ngày đầu VCI khớp báo cáo, ngày sau KBS khớp.

Hai dòng giá lặp tháng 01/2018 không phải phiên thị trường. Thông báo HOSE được
[Báo Chính phủ công bố ngày 24/01/2018](https://baochinhphu.vn/hose-tiep-tuc-ngung-giao-dich-vao-ngay-24-1-102233813.htm)
xác nhận ngừng giao dịch cả 23 và 24/01. Loại chúng khỏi lịch trước khi tạo nhãn;
không được chỉ xóa feature sau khi đã coi chúng là phiên.

Phản hồi broker gốc giữ nguyên trong `sources/`; `manifest.json`,
`index_source_decisions.csv` và sidecar provenance ghi request, hash, giá nguồn,
giá chọn và lý do. Đây là sửa dữ liệu có dấu vết, không tạo giá thay thế từ tương lai.
Bản tải đầu `brokers_2010_20261001` đã bị chặn vì xung đột và được giữ làm đầu vào
replay; chỉ bản có hậu tố `_reviewed` mới là snapshot dùng ở các lệnh tiếp theo.

## Độ phủ nhãn sau khi mở rộng

Giữ nguyên ngưỡng nhãn, feature và thuật toán; chưa train lại hay thử tối ưu điểm.

| Horizon | Baseline riêng từ 2010: giảm / ngang / tăng | Khi so sánh với ETF: giảm / ngang / tăng |
|---|---|---|
| T+20 | 605 / 2.633 / 857 | 295 / 1.524 / 522 |
| T+60 | 399 / 2.837 / 819 | 225 / 1.537 / 539 |
| T+120 | 289 / 2.869 / 837 | 178 / 1.456 / 607 |

So sánh hai bộ feature trên cùng ngày hợp lệ từ 25/02/2016: lần lượt 2.341,
2.301 và 2.241 mẫu. Cả sáu cấu hình dữ liệu qua preflight bốn fold purged.
Baseline riêng có 4.095/4.055/3.995 mẫu. Không so điểm baseline từ 2010 với
ETF từ 2016 như thể chúng cùng giai đoạn. Nhiều nhãn hơn không đảm bảo model tốt hơn.

## Quy trình đánh giá tiếp theo

Nhãn đến 01/10/2026 đã được xem ở lần full trước. `holdout_exposure.json` lưu
mốc này; pipeline còn đọc các report cũ. Full run dùng lại giai đoạn cũ sẽ bị
chặn trước train. Không chọn một holdout lịch sử khác để biến nó thành test mới.

Dùng `--development-only` cho các thí nghiệm tiếp theo trên toàn bộ mẫu có nhãn
đã hoàn tất. Điểm chỉ là CV để chọn cấu hình. Chưa có test mới độc lập hoặc
bằng chứng cải thiện hiệu quả. Khi có dữ liệu sau mốc đã xem và đủ horizon để
nhãn trưởng thành mới có thể dành một giai đoạn cuối mới.

Cần đối chiếu thêm lịch sở giao dịch toàn bộ lịch sử, cổ tức/chia tách ETF và
nguồn/định nghĩa volume trước khi dùng cho quyết định tài chính. Không tự nối
NAV, total return index hoặc volume khác định nghĩa vào chuỗi hiện tại.

Các endpoint broker dùng theo [mã nguồn Vnstock của tác giả](https://github.com/thinh-vu/vnstock/tree/main/vnstock/explorer).
Các endpoint công khai có thể đổi; script lưu lỗi thay vì tạo dữ liệu thay thế.
Lệnh chạy và cách cài môi trường: [REGIME_V2.md](../ml/REGIME_V2.md).
