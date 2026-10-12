n ti

# VAI TRÒ CỦA HỌC MÁY TRONG CƠ CHẾ TÁI CƠ CẤU DANH MỤC ĐỘNG

## SỰ KẾT HỢP GIỮA KHẢO SÁT RỦI RO (SAA), MÁY HỌC (TAA) VÀ TỐI ƯU HÓA MARKOWITZ

### HỆ THỐNG THEO DÕI DANH MỤC VÀ CỐ VẤN TÀI CHÍNH CÁ NHÂN (ROBO-ADVISOR & PORTFOLIO TRACKER)

---

## MỤC LỤC

1. [Đặt vấn đề: Nghịch lý giữa Khảo sát Tĩnh &amp; Thị trường Động](#1-đặt-vấn-đề-nghịch-lý-giữa-khảo-sát-tĩnh--thị-trường-động)
2. [Phân định Bản chất: SAA (Mỏ neo) vs. TAA (Ra-đa Máy học)](#2-phân-định-bản-chất-saa-mỏ-neo-vs-taa-ra-đa-máy-học)
3. [Mô hình Máy học Làm việc Cụ thể Như thế Nào?](#3-mô-hình-máy-học-làm-việc-cụ-thể-như-thế-nào)
   * 3.1. Bản chất: Dự báo Trạng thái Chu kỳ $T+20$ thay vì Đoán giá $T+1$
   * 3.2. Cấu trúc Mô hình Kép Đa Tài sản (Multi-Asset Dual Models)
   * 3.3. Bộ 30+ Đặc trưng Kỹ thuật & Tương quan Liên thị trường
4. [Cơ chế Toán học: Tích hợp Tín hiệu Học máy vào Mô hình Markowitz](#4-cơ-chế-toán-học-tích-hợp-tín-hiệu-học-máy-vào-mô-hình-markowitz)
   * 4.1. Nguồn gốc các biến số trong Hàm Thỏa dụng Markowitz
   * 4.2. Công thức Dịch chuyển Tỷ trọng theo Điểm Tin cậy (Confidence-Weighted Shift)
   * 4.3. Ràng buộc Biên An toàn (Safety Bounds)
5. [Các Kịch bản Minh họa Thực tế (Use Case Walkthroughs)](#5-các-kịch-bản-minh-họa-thực-tế-use-case-walkthroughs)
   * 5.1. Kịch bản 1: Thị trường Cổ phiếu bước vào pha Giảm mạnh (Risk-Off)
   * 5.2. Kịch bản 2: Thị trường Cổ phiếu bước vào pha Tăng trưởng (Risk-On)
   * 5.3. Kịch bản 3: Tín hiệu Đi ngang / Xung đột (Neutral & Sideway)
6. [Phân định Ranh giới Trách nhiệm 4 Tầng Hệ thống](#6-phân-định-ranh-giới-trách-nhiệm-4-tầng-hệ-thống)
7. [Bộ Câu hỏi Trả lời Phản biện trước Hội đồng Chấm Đồ án](#7-bộ-câu-hỏi-trả-lời-phản-biện-trước-hội-đồng-chấm-đồ-án)

---

## 1. Đặt vấn đề: Nghịch lý giữa Khảo sát Tĩnh & Thị trường Động

Trong quản lý danh mục đầu tư cá nhân, một câu hỏi lớn thường được đặt ra:

> *"Nếu hệ thống đã có **Bộ câu hỏi Khảo sát Khẩu vị Rủi ro** để tính ra tỷ trọng mục tiêu (ví dụ: 35% Cổ phiếu, 35% Vàng, 30% Tiết kiệm), thì tại sao lại cần thêm **Mô hình Học máy (Machine Learning)**?"*

Nếu một hệ thống **chỉ dựa vào kết quả khảo sát ban đầu**:

* **Danh mục bị "đóng băng" (Frozen Portfolio):** Tính cách con người rất ít khi thay đổi (vài năm mới đổi một lần), dẫn đến tỷ trọng 35% Cổ phiếu – 35% Vàng – 30% Tiết kiệm sẽ bị cố định mãi mãi.
* **Gánh trọn cú sập của thị trường:** Khi thị trường chứng khoán bước vào chu kỳ khủng hoảng, suy thoái sâu (như giai đoạn năm 2022 khi chỉ số VN-Index rơi từ 1.500 điểm về 900 điểm), danh mục của người dùng sẽ **hứng trọn mức sụt giảm nghiêm trọng** mà không có bất kỳ phản xạ tự vệ nào.

Ngược lại, thị trường tài chính là một thực thể vận động không ngừng theo các chu kỳ vĩ mô. Do đó, hệ thống cần một cơ chế thông minh để kết hợp giữa **khung an toàn của con người** và **nhịp thở thực tế của thị trường**.

---

## 2. Phân định Bản chất: SAA (Mỏ neo) vs. TAA (Ra-đa Máy học)

Hệ thống phân tách bài toán phân bổ tài sản thành hai cấp độ chuẩn mực theo lý thuyết quản trị danh mục hiện đại:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. CHIẾN LƯỢC DÀI HẠN: STRATEGIC ASSET ALLOCATION (SAA)                │
│    Nguồn gốc: BỘ KHẢO SÁT KHẨU VỊ RỦI RO CỦA NGƯỜI DÙNG                │
│    Bản chất: Đóng vai trò là "CỘT MỐC NEO AN TOÀN" (Mỏ neo)            │
│    Chu kỳ thay đổi: Rất chậm (1 - 3 năm hoặc khi hoàn cảnh sống đổi)   │
│    Đầu ra: Hồ sơ rủi ro, Hệ số ngại rủi ro λ, Tỷ trọng chuẩn           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. CHIẾN THUẬT LINH HOẠT: TACTICAL ASSET ALLOCATION (TAA)              │
│    Nguồn gốc: MÔ HÌNH HỌC MÁY (LIGHTGBM QUA ONNX RUNTIME)              │
│    Bản chất: Đóng vai trò là "HỆ THỐNG RA-ĐA CẢNH BÁO THỜI TIẾT"       │
│    Chu kỳ thay đổi: Hàng tháng (T+20 phiên giao dịch)                  │
│    Đầu ra: Dự báo xu hướng chu kỳ (Bullish / Sideway / Bearish) + P    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. ĐIỀU PHỐI TOÁN HỌC: PORTFOLIO OPTIMIZER (JAVA MARKOWITZ MVO)        │
│    Giải bài toán tối ưu lồi: Dịch chuyển tỷ trọng TAA quanh mốc neo    │
│    SAA trong một biên độ an toàn nghiêm ngặt (Safety Band ±15%)        │
└────────────────────────────────────────────────────────────────────────┘
```

| Tiêu chí                       | Phân bổ Chiến lược (SAA)                                           | Phân bổ Chiến thuật (TAA bằng ML)                                              |
| :------------------------------- | :---------------------------------------------------------------------- | :---------------------------------------------------------------------------------- |
| **Quyết định bởi**     | **Con người** (Bộ câu hỏi khảo sát rủi ro).               | **Thị trường khách quan** (Mô hình Học máy).                          |
| **Vai trò**               | Thiết lập "Vùng an toàn tối đa" và khẩu vị rủi ro$\lambda$. | Phát hiện "Thời tiết thị trường" để co cụm phòng thủ hoặc đón sóng. |
| **Đặc tính**            | Tĩnh, dài hạn, bảo vệ tâm lý nhà đầu tư.                     | Động, thích ứng linh hoạt theo từng chu kỳ 1 tháng ($T+20$).              |
| **Nếu đứng một mình** | Danh mục chậm chạp, chịu trận khi thị trường sập.              | Dễ bị cuốn vào biến động thị trường nếu không có mỏ neo kiềm chế.   |

---

## 3. Mô hình Máy học Làm việc Cụ thể Như thế Nào?

### 3.1. Bản chất: Dự báo Trạng thái Chu kỳ $T+20$ thay vì Đoán giá $T+1$

* **Tại sao không dự báo ngày mai ($T+1, T+3$)?** Trong tài chính học thuật, giá ngắn hạn theo ngày bị chi phối nặng nề bởi **Nhiễu ngẫu nhiên (White Noise)**, tâm lý bầy đàn và hành vi thao túng của đội lái. Dự báo giá $T+1$ về bản chất xác suất chỉ quanh 50% (tương đương tung đồng xu).
* **Tại sao chọn chu kỳ 1 tháng ($T+20$ phiên nến ngày)?**
  * Khớp với chu kỳ dòng tiền cá nhân (nhận lương, trả lãi tiết kiệm hàng tháng).
  * Đủ dài để triệt tiêu nhiễu vi mô hàng ngày, phản ánh đúng **động lực dòng tiền lớn của khối ngoại/tổ chức và xu hướng vĩ mô trung hạn (Macro Regime)**.
  * Giúp mô hình LightGBM đạt Macro F1-score $> 0.60$ và độ chính xác $> 63\%$, mang giá trị ứng dụng thực tế cao.

### 3.2. Cấu trúc Mô hình Kép Đa Tài sản (Multi-Asset Dual Models)

Hệ thống không dùng một mô hình gộp mà triển khai **2 mô hình độc lập** được tối ưu hóa riêng cho từng lớp tài sản:

```
[ Dữ liệu Nến ngày OHLCV 2018 - 2026 ]
               │
               ▼
[ Trích xuất 30+ Đặc trưng Kỹ thuật ]
               │
       ┌───────┴───────┐
       ▼               ▼
[ Model 1: VN30 ]   [ Model 2: Vàng SJC/Thế giới ]
(stock_regime.onnx) (gold_trend.onnx)
       │               │
       ▼               ▼
Nhãn: +1, 0, -1     Nhãn: +1, 0, -1
Kèm độ tin cậy P    Kèm độ tin cậy P
```

1. **Mô hình Cổ phiếu (`stock_regime.onnx`):**
   * **Nhãn `+1` (Bullish / Risk-On):** Lợi nhuận $T+20 > +5.0\%$ $\rightarrow$ Thị trường vào sóng tăng trưởng.
   * **Nhãn `0` (Neutral / Sideway):** Lợi nhuận $T+20 \in [-5.0\%, +5.0\%]$ $\rightarrow$ Thị trường tích lũy đi ngang.
   * **Nhãn `-1` (Bearish / Risk-Off):** Lợi nhuận $T+20 < -5.0\%$ $\rightarrow$ Thị trường suy yếu, rủi ro điều chỉnh sâu.
2. **Mô hình Vàng (`gold_trend.onnx`):**
   * **Nhãn `+1` (Bullish):** Lợi nhuận Vàng $T+20 > +3.0\%$ $\rightarrow$ Vàng vào chu kỳ tăng giá (nhu cầu trú ẩn hoặc áp lực lạm phát).
   * **Nhãn `0` (Neutral):** Lợi nhuận Vàng $T+20 \in [-3.0\%, +3.0\%]$ $\rightarrow$ Giá vàng ổn định.
   * **Nhãn `-1` (Bearish):** Lợi nhuận Vàng $T+20 < -3.0\%$ $\rightarrow$ Giá vàng hạ nhiệt, dòng tiền ưu tiên tài sản sinh lời khác.

### 3.3. Bộ 30+ Đặc trưng Kỹ thuật & Tương quan Liên thị trường

Mô hình học máy không chỉ đọc giá đóng cửa mà trích xuất bộ đặc trưng đa chiều:

* **Chỉ báo động lượng & xu hướng:** RSI(14), MACD Histogram, Bollinger Bands, SMA/EMA (20, 50).
* **Chỉ báo biến động rủi ro (Volatility):** Average True Range (ATR), Độ lệch chuẩn lăn (Rolling Standard Deviation 20 ngày).
* **Đặc trưng tương quan liên thị trường (Cross-Asset Features):**
  * Tỷ lệ giá Vàng trên VN-Index (Gold-to-Equity Ratio).
  * Hệ số tương quan động lăn 30 ngày giữa Cổ phiếu và Vàng $\rightarrow$ Làm chỉ báo sớm về việc dòng tiền đang tìm nơi trú ẩn hay đang mạo hiểm tìm kiếm lợi nhuận.

---

## 4. Cơ chế Toán học: Tích hợp Tín hiệu Học máy vào Mô hình Markowitz

### 4.1. Nguồn gốc các biến số trong Hàm Thỏa dụng Markowitz

Bài toán Tối ưu hóa Danh mục Hiện đại (Mean-Variance Optimization - MVO):

$$
\max_{w} U(w) = w^T \mu(t) - \frac{1}{2} \lambda \cdot (w^T \Sigma(t) w)
$$

với hệ ràng buộc: $\sum_{i=1}^{n} w_i = 1$ và $w_i \ge 0$ (Không bán khống - Long-only).

Trong công thức trên:

1. **Hệ số $\lambda$ (Lambda - Mức độ ngại rủi ro):** Được lấy từ **Bộ Khảo sát Rủi ro của Người dùng** ($\lambda \in [1.0, 10.0]$). Tham số này giữ nguyên bản sắc cá nhân của người dùng, không bị ML thay đổi.
2. **Vector Lợi nhuận kỳ vọng $\mu(t)$:** Không dùng trung bình quá khứ tĩnh, mà được điều chỉnh động theo **Nhãn dự báo và Xác suất của mô hình ML**:
   $$
   \mu_i(t) = \mu_{i, \text{lịch sử}} \times \left(1 + \text{Signal}_i \times P_{\text{confidence}, i}\right)
   $$
3. **Ma trận Hiệp phương sai $\Sigma(t)$:** Cập nhật độ biến động $\sigma_i^2$ theo chỉ báo ATR và Volatility mới nhất từ tầng feature engineering của ML.

---

### 4.2. Công thức Dịch chuyển Tỷ trọng theo Điểm Tin cậy (Confidence-Weighted Shift)

Để đảm bảo an toàn tuyệt đối và tính ổn định, hệ thống quy định biên độ dịch chuyển tỷ trọng chiến thuật (Tactical Shift $\Delta w_i$) tỷ lệ thuận với **Độ tin cậy của Machine Learning**:

$$
\Delta w_i = \text{Signal}_i \times P_{\text{confidence}} \times \Delta w_{\max}
$$

*Trong đó:*

* $\text{Signal}_i \in \{+1, 0, -1\}$: Tín hiệu định hướng từ mô hình ONNX.
* $P_{\text{confidence}} \in [0.0, 1.0]$: Xác suất dự báo của lớp nhãn thắng thế.
* $\Delta w_{\max} = 15\%$: Biên độ dịch chuyển tối đa cho phép trong một chu kỳ tái cơ cấu.

---

### 4.3. Ràng buộc Biên An toàn (Safety Bounds)

Học máy có thể dự báo sai trong những tình huống bất ngờ (Black Swan). Để bảo vệ người dùng, thuật toán tối ưu hóa trong Java áp dụng nguyên tắc **Biên an toàn (Safety Collars)**: Tỷ trọng chiến thuật sau điều chỉnh $w_i^{\text{TAA}}$ **tuyệt đối không bao giờ được vượt ra ngoài dải biên độ quanh tỷ trọng chiến lược neo $w_i^{\text{SAA}}$**:

$$
w_i^{\text{SAA}} - \Delta w_{\max} \le w_i^{\text{TAA}} \le w_i^{\text{SAA}} + \Delta w_{\max}
$$

*Ví dụ:* Với người dùng nhóm Cân bằng có $w_{\text{Cổ phiếu}}^{\text{SAA}} = 35\%$:

* Dù mô hình ML có lạc quan $100\%$ Bullish, tỷ trọng Cổ phiếu tối đa chỉ được nâng lên: $35\% + 15\% = \mathbf{50\%}$.
* Dù mô hình ML có bi quan $100\%$ Bearish, tỷ trọng Cổ phiếu cũng không bị bán sạch về 0 mà chặn dưới ở mức: $35\% - 15\% = \mathbf{20\%}$.
* Phần vốn dôi dư luôn được chuyển sang **Tiền gửi tiết kiệm ngân hàng (Tài sản phi rủi ro $R_f$)** để bảo toàn vốn gốc.

---

## 5. Các Kịch bản Minh họa Thực tế (Use Case Walkthroughs)

Giả sử Nhà đầu tư Nguyễn Văn A làm khảo sát rủi ro đạt điểm 55 (Nhóm Cân bằng), tỷ trọng neo ban đầu (SAA) là:

$$
\text{SAA} = \{ \text{Cổ phiếu}: 35\%, \text{Vàng}: 35\%, \text{Tiết kiệm}: 30\% \}
$$

---

### 5.1. Kịch bản 1: Thị trường Cổ phiếu bước vào pha Giảm mạnh (Risk-Off)

* **Bối cảnh thị trường:** Chỉ số VN-Index gãy MA50, RSI phân kỳ âm, tỷ lệ Vàng/Cổ phiếu tăng vọt.
* **Suy luận Máy học:**
  * Model Cổ phiếu: Nhãn `-1` (Bearish), độ tin cậy $P = 0.80$.
  * Model Vàng: Nhãn `+1` (Bullish), độ tin cậy $P = 0.75$.
* **Tính toán Tái cơ cấu (Java Optimizer):**
  * Tỷ trọng Cổ phiếu giảm: $\Delta w = -1 \times 0.80 \times 15\% = -12\% \implies w_{\text{Cổ phiếu}} = 35\% - 12\% = \mathbf{23\%}$.
  * Tỷ trọng Vàng tăng: $\Delta w = +1 \times 0.75 \times 10\% = +7.5\% \implies w_{\text{Vàng}} = 35\% + 7.5\% = \mathbf{42.5\%}$.
  * Tiền gửi tiết kiệm tăng để hấp thụ phần vốn bảo thủ: $w_{\text{Tiết kiệm}} = \mathbf{34.5\%}$.
* **Hành động của Copilot:** Copilot đưa ra bảng kế hoạch hành động: Khuyên bán bớt một phần cổ phiếu (ví dụ chốt lời HPG), mua thêm 2 chỉ vàng SJC và mở sổ tiết kiệm 3 tháng để bảo vệ thành quả.
* **Kết quả:** Khi thị trường cổ phiếu giảm mạnh trong tháng tiếp theo, danh mục của người dùng được bảo vệ an toàn nhờ tỷ trọng Vàng và Tiền gửi lớn gánh đỡ.

---

### 5.2. Kịch bản 2: Thị trường Cổ phiếu bước vào pha Tăng trưởng (Risk-On)

* **Bối cảnh thị trường:** Dòng tiền thanh khoản bùng nổ, khối ngoại mua ròng, đường MACD cắt lên đường tín hiệu.
* **Suy luận Máy học:**
  * Model Cổ phiếu: Nhãn `+1` (Bullish), độ tin cậy $P = 0.85$.
  * Model Vàng: Nhãn `0` (Neutral), độ tin cậy $P = 0.60$.
* **Tính toán Tái cơ cấu (Java Optimizer):**
  * Tỷ trọng Cổ phiếu tăng: $\Delta w = +1 \times 0.85 \times 15\% = +12.75\% \implies w_{\text{Cổ phiếu}} \approx \mathbf{47.75\%}$.
  * Tỷ trọng Tiền mặt/Tiết kiệm đáo hạn rút ra giải ngân vào cổ phiếu rổ VN30.
* **Kết quả:** Giúp danh mục không bị bỏ lỡ con sóng tăng trưởng của nền kinh tế, tối ưu hóa lợi nhuận kỳ vọng.

---

### 5.3. Kịch bản 3: Tín hiệu Đi ngang / Xung đột (Neutral & Sideway)

* **Suy luận Máy học:** Cả hai mô hình đều báo nhãn `0` hoặc độ tin cậy $P < 0.50$ (thị trường giằng co, xu hướng không rõ ràng).
* **Tính toán:** $\Delta w \approx 0\%$.
* **Hành động:** Hệ thống giữ nguyên tỷ trọng SAA ban đầu (35% – 35% – 30%), khuyên người dùng tiếp tục nắm giữ kỷ luật, tránh mua bán liên tục gây tốn phí giao dịch và thuế.

---

## 6. Phân định Ranh giới Trách nhiệm 4 Tầng Hệ thống

Để đảm bảo tính chuyên nghiệp và tính an toàn của phần mềm tài chính, trách nhiệm giữa các phân hệ được phân định rạch ròi, triệt tiêu hoàn toàn hiện tượng AI "ảo giác" (Hallucination):

```
┌────────────────────────────────────────────────────────────────────────┐
│ TẦNG 1: BỘ KHẢO SÁT RỦI RO (User Risk Survey)                         │
│ • Trách nhiệm: Định hình Khung an toàn tối đa và Hệ số ngại rủi ro λ.  │
│ • Tính chất: Tĩnh, thiết lập nền tảng tâm lý học hành vi.              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TẦNG 2: MÔ HÌNH HỌC MÁY (LightGBM via Embedded ONNX Runtime)           │
│ • Trách nhiệm: Ra-đa dự báo thời tiết chu kỳ T+20 (Nhãn & Xác suất P). │
│ • Tính chất: Động, suy luận song song trong RAM JVM < 3ms.             │
│ • TUYỆT ĐỐI KHÔNG: Tự ý sinh ra số tiền hay % tỷ trọng danh mục.       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TẦNG 3: BỘ TỐI ƯU HÓA DANH MỤC (Java Core Portfolio Optimizer)         │
│ • Trách nhiệm: Nhận đầu vào từ Tầng 1 + Tầng 2 + Số dư Sổ cái kép.     │
│ • Giải bài toán toán học xác định (Deterministic Markowitz MVO).       │
│ • Làm tròn khối lượng giao dịch thực tế: Lô 100 cổ phiếu, bước chỉ vàng│
│ • Xuất ra hợp đồng dữ liệu chuẩn Structured JSON (Kế hoạch hành động). │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TẦNG 4: TRỢ LÝ TÀI CHÍNH THÔNG MINH (Spring AI Financial Copilot)      │
│ • Trách nhiệm: Nhận JSON từ Tầng 3 và giải thích cho người dùng hiểu.  │
│ • Áp dụng Zero-Trust Tool Calling + In-Database RRF Hybrid Search.     │
│ • TUYỆT ĐỐI KHÔNG: Tự bịa số tiền; áp dụng Human-in-the-Loop.          │
│ • Người dùng duyệt ở ngoài đời $\rightarrow$ Bút toán Sổ cái mới ghi. │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Bộ Câu hỏi Trả lời Phản biện trước Hội đồng Chấm Đồ án

Khi Hội đồng giám khảo đặt câu hỏi chất vấn, bạn có thể tự tin trả lời theo các luận điểm sau:

#### Câu hỏi 1: "Tại sao em không dùng mô hình Học máy để dự đoán chính xác giá cổ phiếu ngày mai tăng bao nhiêu đồng?"

> **Trả lời:**
> *"Thưa Thầy/Cô, việc dự báo giá chính xác ngắn hạn $T+1$ vi phạm giả thuyết thị trường hiệu quả và bị chi phối bởi nhiễu ngẫu nhiên (White Noise). Trong quản lý tài chính cá nhân, nhà đầu tư tích sản không lướt sóng hàng ngày. Em chọn bài toán phân loại trạng thái chu kỳ 1 tháng ($T+20$ phiên) để phản ánh đúng xu hướng vĩ mô trung hạn và chu kỳ tích sản, giúp mô hình đạt độ chính xác khoa học và mang tính ứng dụng thực tiễn cao."*

#### Câu hỏi 2: "Nếu mô hình Học máy dự báo sai thì danh mục của người dùng có bị sụp đổ không?"

> **Trả lời:**
> *"Dạ không thể sụp đổ được ạ, vì hệ thống của em thiết kế cơ chế **Biên an toàn (Safety Bounds)**: Tỷ trọng do ML đề xuất luôn bị chặn trần/chặn sàn trong biên độ $\pm 15\%$ quanh tỷ trọng mỏ neo SAA do người dùng tự xác lập. Ngoài ra, danh mục luôn duy trì tỷ lệ Tiền gửi tiết kiệm tối thiểu (tài sản phi rủi ro) làm bộ đệm chống sốc, và quyết định cuối cùng vẫn thuộc về người dùng (Human-in-the-Loop) chứ hệ thống không tự ý đặt lệnh."*

#### Câu hỏi 3: "Tại sao không để cho con AI Copilot (LLM) tự tính toán tỷ trọng luôn mà phải dùng thuật toán Java Markowitz riêng?"

> **Trả lời:**
> *"Trong kỹ thuật phần mềm tài chính, mô hình ngôn ngữ lớn (LLM) tiềm ẩn rủi ro ảo giác (Hallucination) và tính toán số học không tin cậy. Em áp dụng nguyên tắc **Separation of Concerns**: Toàn bộ việc tính toán tiền bạc, tỷ trọng và làm tròn lô chẵn 100 cổ phiếu được thực thi bởi thuật toán toán học xác định (Deterministic Algorithm) trong Java. LLM chỉ đóng vai trò là giao diện giao tiếp tự nhiên để giải thích kế hoạch toán học đó cho người dùng dễ hiểu."*
