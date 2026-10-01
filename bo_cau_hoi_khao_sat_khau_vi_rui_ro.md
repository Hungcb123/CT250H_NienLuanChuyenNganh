# ĐẶC TẢ BỘ CÂU HỎI KHẢO SÁT KHẨU VỊ RỦI RO & MÔ HÌNH HÓA TOÁN HỌC
## HỆ THỐNG THEO DÕI DANH MỤC VÀ CỐ VẤN TÀI CHÍNH CÁ NHÂN (ROBO-ADVISOR & PORTFOLIO TRACKER)

---

## MỤC LỤC
1. [Tổng quan & Cơ sở Lý thuyết Thẩm định Rủi ro](#1-tổng-quan--cơ-sở-lý-thuyết-thẩm-định-rủi-ro)
2. [Chi tiết Bộ 5 Câu hỏi Chuẩn hóa (Thang điểm 100)](#2-chi-tiết-bộ-5-câu-hỏi-chuẩn-hóa-thang-điểm-100)
   * [Câu 1: Kỳ hạn đầu tư dự kiến (Investment Horizon)](#câu-1-kỳ-hạn-đầu-tư-dự-kiến-investment-horizon)
   * [Câu 2: Tính ổn định dòng tiền & Quỹ khẩn cấp (Cashflow & Emergency Buffer)](#câu-2-tính-ổn-định-dòng-tiền--quỹ-khẩn-cấp-cashflow--emergency-buffer)
   * [Câu 3: Mục tiêu tài chính ưu tiên (Primary Financial Goal)](#câu-3-mục-tiêu-tài-chính-ưu-tiên-primary-financial-goal)
   * [Câu 4: Thử nghiệm ứng xử khi thị trường sụt giảm mạnh (Drawdown Reaction Stress-Test)](#câu-4-thử-nghiệm-ứng-xử-khi-thị-trường-sụt-giảm-mạnh-drawdown-reaction-stress-test)
   * [Câu 5: Kinh nghiệm & Kiến thức tài sản thực tế (Asset Literacy & Experience)](#câu-5-kinh-nghiệm--kiến-thức-tài-sản-thực-tế-asset-literacy--experience)
3. [Mô hình Hóa Toán học & Công thức Ánh xạ](#3-mô-hình-hóa-toán-học--công-thức-ánh-xạ)
   * [3.1. Tính toán Điểm Rủi ro Tổng hợp (Risk Score)](#31-tính-toán-điểm-rủi-ro-tổng-hợp-risk-score)
   * [3.2. Ánh xạ sang Hệ số Ngại Rủi ro ($\lambda$ - Lambda)](#32-ánh-xạ-sang-hệ-số-ngại-rủi-ro--lambda---lambda)
   * [3.3. Ma trận Phân nhóm & Tỷ trọng Chiến lược Neo (SAA Baseline)](#33-ma-trận-phân-nhóm--tỷ-trọng-chiến-lược-neo-saa-baseline)
4. [Tích hợp Phần mềm & Hợp đồng Dữ liệu (API Contract)](#4-tích-hợp-phần-mềm--hợp-đồng-dữ-liệu-api-contract)
   * [4.1. Lưu trữ Cơ sở Dữ liệu (PostgreSQL Schema)](#41-lưu-trữ-cơ-sở-dữ-liệu-postgresql-schema)
   * [4.2. Đặc tả API Endpoint (JSON Interface)](#42-đặc-tả-api-endpoint-json-interface)
   * [4.3. Cá nhân hóa Trợ lý Financial Copilot (Zero-Trust Context)](#43-cá-nhân-hóa-trợ-lý-financial-copilot-zero-trust-context)

---

## 1. Tổng quan & Cơ sở Lý thuyết Thẩm định Rủi ro

Trong quản trị tài sản cá nhân và cố vấn tự động (Robo-Advisory), việc xác định khẩu vị rủi ro không thể thực hiện qua những câu hỏi phán đoán cảm tính. Hệ thống áp dụng khung lý thuyết thẩm định chuẩn hóa theo tiêu chuẩn **MiFID II (Châu Âu)** và **SEC Rule 206(4)-7 (Hoa Kỳ)**, phân tách rõ ràng hai trục đo lường độc lập:

1. **Khả năng chịu rủi ro (Risk Capacity - Năng lực tài chính khách quan):** 
   * Trả lời câu hỏi: *“Nhà đầu tư CÓ THỂ chịu được mức lỗ bao nhiêu mà không bị phá sản hoặc ảnh hưởng tới chi phí sinh hoạt tối thiểu?”*.
   * Được lượng hóa qua: Thời gian dự kiến nắm giữ tài sản, tính ổn định của dòng thu nhập thặng dư, và quy mô quỹ dự phòng khẩn cấp.
2. **Sẵn sàng chịu rủi ro (Risk Tolerance - Tâm lý chịu đựng chủ quan):**
   * Trả lời câu hỏi: *“Nhà đầu tư DÁM nhìn tài sản biến động sụt giảm bao nhiêu % trong ngắn hạn mà không hoảng loạn đưa ra quyết định sai lầm?”*.
   * Được lượng hóa qua: Mục tiêu ưu tiên bảo toàn vốn so với sinh lời, hành vi phản ứng trước các đợt sụt giảm sâu (Drawdown), và kinh nghiệm thực chiến trên thị trường tài chính.

---

## 2. Chi tiết Bộ 5 Câu hỏi Chuẩn hóa (Thang điểm 100)

Bộ câu hỏi gồm **5 câu hỏi trắc nghiệm**, mỗi câu gồm 4 lựa chọn tương ứng với thang điểm tuyến tính: **0 – 7 – 14 – 20 điểm**. Tổng điểm tối đa là **100 điểm**.

---

### Câu 1: Kỳ hạn đầu tư dự kiến (Investment Horizon)
> **Nội dung:** *"Khoản tiền bạn đưa vào hệ thống này dự kiến sẽ duy trì đầu tư tích sản trong bao lâu mà không cần rút ra để chi tiêu?"*

| Phương án | Nội dung lựa chọn | Điểm số |
| :---: | :--- | :---: |
| **A** | Dưới 1 năm | **0 điểm** |
| **B** | Từ 1 năm đến dưới 3 năm | **7 điểm** |
| **C** | Từ 3 năm đến dưới 5 năm | **14 điểm** |
| **D** | Từ 5 năm trở lên (Dài hạn tích sản) | **20 điểm** |

* **Bản chất tài chính:** Kỳ hạn đầu tư quyết định khả năng vượt qua các chu kỳ suy thoái của thị trường. Cổ phiếu có độ biến động ngắn hạn lớn nhưng có xu hướng tăng trưởng trong dài hạn. Nếu dòng tiền chỉ rảnh rỗi dưới 1 năm, hệ thống **bắt buộc phải ưu tiên Tiền gửi ngắn hạn hoặc Tiền mặt**, triệt tiêu nguy cơ người dùng bị buộc phải bán tháo cổ phiếu đúng đáy để rút tiền sinh hoạt.
* **Tác động thuật toán:** Kỳ hạn càng dài ($> 3$ năm) $\rightarrow$ Tăng giới hạn trần tỷ trọng Cổ phiếu được phép phân bổ trong bộ tối ưu hóa Markowitz.

---

### Câu 2: Tính ổn định dòng tiền & Quỹ khẩn cấp (Cashflow & Emergency Buffer)
> **Nội dung:** *"Tình hình tài chính và dòng tiền tiết kiệm hàng tháng của bạn hiện tại như thế nào?"*

| Phương án | Nội dung lựa chọn | Điểm số |
| :---: | :--- | :---: |
| **A** | Thu nhập bấp bênh, hầu như không có dư dả hàng tháng hoặc đang có nợ phải trả | **0 điểm** |
| **B** | Dư khoảng 10% – 20% thu nhập mỗi tháng, nhưng chưa có quỹ dự phòng khẩn cấp | **7 điểm** |
| **C** | Thu nhập ổn định, dư 20% – 40% mỗi tháng và đã có quỹ dự phòng 3 – 6 tháng chi phí sinh hoạt | **14 điểm** |
| **D** | Dòng tiền thặng dư trên 40% thu nhập, nguồn thu nhập dồi dào, quỹ dự phòng vững chắc | **20 điểm** |

* **Bản chất tài chính:** Đảm bảo nguyên tắc bảo toàn vốn sinh kế. Người dùng chưa có quỹ dự phòng khẩn cấp không được phép giải ngân vào các tài sản biến động mạnh. Dòng tiền thặng dư đều đặn là điều kiện tiên quyết để thực thi chiến lược mua gom bình quân giá (Dollar-Cost Averaging - DCA) khi thị trường điều chỉnh.
* **Tác động thuật toán:** Điểm thấp $\rightarrow$ Ép tỷ trọng Tiền gửi tiết kiệm tối thiểu $\ge 50\%$; Điểm cao $\rightarrow$ Cho phép nâng tỷ trọng các tài sản tăng trưởng.

---

### Câu 3: Mục tiêu tài chính ưu tiên (Primary Financial Goal)
> **Nội dung:** *"Mục tiêu quan trọng nhất của bạn đối với danh mục tài sản này là gì?"*

| Phương án | Nội dung lựa chọn | Điểm số |
| :---: | :--- | :---: |
| **A** | **Tuyệt đối an toàn:** Bảo toàn vốn gốc là ưu tiên số 1, lợi nhuận chỉ cần ngang hoặc nhỉnh hơn lạm phát một chút | **0 điểm** |
| **B** | **Thận trọng:** Chấp nhận biến động rất nhỏ để đạt tỷ suất sinh lời cao hơn lãi suất tiết kiệm ngân hàng | **7 điểm** |
| **C** | **Tăng trưởng cân bằng:** Chấp nhận biến động vừa phải để tăng trưởng vốn đều đặn trong trung và dài hạn | **14 điểm** |
| **D** | **Tối đa hóa tài sản:** Sẵn sàng chịu những đợt rung lắc mạnh để tối ưu hóa hiệu suất lợi nhuận cao nhất | **20 điểm** |

* **Bản chất tài chính:** Xác định kỳ vọng lợi nhuận biên của nhà đầu tư, làm cơ sở định hình hàm mục tiêu tối ưu hóa danh mục: Thiên về **Tối thiểu hóa phương sai rủi ro ($\min \sigma_p^2$)** hay **Tối đa hóa lợi nhuận kỳ vọng ($\max E(R_p)$)**.
* **Tác động thuật toán:** Quyết định việc lựa chọn danh mục nằm ở điểm nào trên Đường biên hiệu quả (Efficient Frontier).

---

### Câu 4: Thử nghiệm ứng xử khi thị trường sụt giảm mạnh (Drawdown Reaction Stress-Test)
> **Nội dung:** *"Giả sử sau 1 tháng, do thị trường biến động tiêu cực, tổng giá trị danh mục của bạn bị giảm -15%. Phản ứng thực tế của bạn sẽ là:"*

| Phương án | Nội dung lựa chọn | Điểm số |
| :---: | :--- | :---: |
| **A** | Rất hoảng loạn, mất ngủ và bấm bán tháo toàn bộ danh mục để gửi tiết kiệm ngân hàng | **0 điểm** |
| **B** | Cảm thấy lo âu, quyết định bán bớt 50% danh mục để thu tiền mặt về bảo toàn phần vốn còn lại | **7 điểm** |
| **C** | Bình tĩnh theo dõi, giữ nguyên danh mục vì hiểu rõ thị trường biến động có chu kỳ | **14 điểm** |
| **D** | Hào hứng xem đây là cơ hội vàng, chủ động trích thêm tiền nhàn rỗi để mua gom tích sản giá rẻ | **20 điểm** |

* **Bản chất tài chính:** Đo lường mức độ ác cảm thua lỗ (Loss Aversion). Trong kinh tế học hành vi (Behavioral Economics), nỗi đau mất tiền thường gấp 2.5 lần niềm vui kiếm được tiền. Đây là câu hỏi quyết định trọng số lớn nhất trong việc tinh chỉnh hệ số $\lambda$.
* **Tác động thuật toán:** Người dùng chọn A hoặc B sẽ bị áp hệ số $\lambda$ cao để giảm tỷ trọng Cổ phiếu, tránh tình trạng hoảng loạn cắt lỗ khi thị trường rung lắc.

---

### Câu 5: Kinh nghiệm & Kiến thức tài sản thực tế (Asset Literacy & Experience)
> **Nội dung:** *"Bạn đã từng có kinh nghiệm trực tiếp đầu tư hoặc quản lý các kênh tài sản nào sau đây?"*

| Phương án | Nội dung lựa chọn | Điểm số |
| :---: | :--- | :---: |
| **A** | Chưa từng đầu tư, trước giờ chỉ gửi tiết kiệm ngân hàng truyền thống hoặc giữ tiền mặt | **0 điểm** |
| **B** | Đã từng mua vàng tích trữ (vàng miếng SJC hoặc vàng nhẫn 9999) và theo dõi giá vàng | **7 điểm** |
| **C** | Đã từng mở tài khoản chứng khoán hoặc mua chứng chỉ quỹ mở, thời gian tham gia dưới 1 năm | **14 điểm** |
| **D** | Đã đầu tư chứng khoán trên 2 năm, hiểu rõ chu kỳ thị trường và các nguyên tắc phân tích kỹ thuật/cơ bản | **20 điểm** |

* **Bản chất tài chính:** Đo lường trải nghiệm thực tế với các bước giá, chu kỳ khớp lệnh và rủi ro thanh khoản. Người chưa có kinh nghiệm dễ bị tâm lý đám đông dẫn dắt (FOMO hoặc Panic Selling).
* **Tác động thuật toán & Copilot:**
  * Thuật toán: Hạn chế phân bổ các tài sản phức tạp cho người chưa có kinh nghiệm.
  * Copilot (Spring AI): Cá nhân hóa văn phong tư vấn. Người ít kinh nghiệm nhận được lời giải thích đơn giản, trực quan, hướng dẫn từng bước đặt lệnh; người có kinh nghiệm nhận được phân tích chuyên sâu về các chỉ báo kinh tế vĩ mô và kỹ thuật.

---

## 3. Mô hình Hóa Toán học & Công thức Ánh xạ

### 3.1. Tính toán Điểm Rủi ro Tổng hợp (Risk Score)

Tổng điểm khảo sát được chuẩn hóa về đoạn $[0, 100]$:

$$\text{Risk Score} = \sum_{i=1}^{5} \text{Điểm}_i \quad \in [0, 100]$$

---

### 3.2. Ánh xạ sang Hệ số Ngại Rủi ro ($\lambda$ - Lambda)

Trong mô hình Tối ưu hóa Danh mục Hiện đại của Markowitz (Mean-Variance Optimization - MVO), hàm thỏa dụng (Utility Function) của nhà đầu tư được định nghĩa:

$$U(w) = E(R_p) - \frac{1}{2} \lambda \sigma_p^2$$

Trong đó:
* $E(R_p)$: Tỷ suất sinh lời kỳ vọng của danh mục.
* $\sigma_p^2$: Mức độ rủi ro (phương sai) biến động của danh mục.
* $\lambda$ (Lambda): Hệ số ngại rủi ro. $\lambda$ càng lớn thì mức phạt rủi ro càng nặng, thuật toán càng ưu tiên tài sản an toàn.

Hệ thống thiết lập cận biên:
* $\lambda_{\min} = 1.0$ (Dành cho nhà đầu tư mạo hiểm nhất, chấp nhận rủi ro cao để tối đa hóa lợi nhuận).
* $\lambda_{\max} = 10.0$ (Dành cho nhà đầu tư cực kỳ thận trọng, đặt sự an toàn vốn lên hàng đầu).

**Công thức ánh xạ toán học liên tục:**

$$\lambda = \lambda_{\max} - \left(\frac{\text{Risk Score}}{100}\right) \times (\lambda_{\max} - \lambda_{\min})$$

Thay số thực tế:

$$\lambda = 10.0 - \left(\frac{\text{Risk Score}}{100}\right) \times (10.0 - 1.0) = \mathbf{10.0 - 0.09 \times \text{Risk Score}}$$

*Ví dụ minh họa:*
* Điểm $\text{Risk Score} = 80 \implies \lambda = 10.0 - 0.09 \times 80 = 2.8$ (Nhóm Tăng trưởng).
* Điểm $\text{Risk Score} = 50 \implies \lambda = 10.0 - 0.09 \times 50 = 5.5$ (Nhóm Cân bằng).
* Điểm $\text{Risk Score} = 20 \implies \lambda = 10.0 - 0.09 \times 20 = 8.2$ (Nhóm Bảo thủ).

---

### 3.3. Ma trận Phân nhóm & Tỷ trọng Chiến lược Neo (SAA Baseline)

Từ điểm số chuẩn hóa, hệ thống phân loại nhà đầu tư thành 3 phân nhóm hồ sơ và gán cơ cấu tỷ trọng phân bổ tài sản chiến lược ban đầu (Strategic Asset Allocation - SAA):

| Nhóm Hồ sơ (Risk Profile) | Thang điểm $\text{Risk Score}$ | Biên độ $\lambda$ | Tỷ trọng Mục tiêu Ban đầu (SAA Baseline) | Khuyến nghị Hành vi |
| :--- | :---: | :---: | :--- | :--- |
| **Bảo thủ (Conservative)** | $0 \le \text{Score} < 40$ | $7.0 \le \lambda \le 10.0$ | **60% Tiết kiệm/Tiền mặt**<br>**25% Vàng vật chất**<br>**15% Cổ phiếu VN30** | Ưu tiên bảo toàn vốn, dòng tiền ổn định, phòng hộ trượt giá lạm phát qua vàng, tỷ trọng cổ phiếu chỉ mang tính tích lũy nhận cổ tức. |
| **Cân bằng (Balanced)** | $40 \le \text{Score} < 70$ | $4.0 \le \lambda < 7.0$ | **30% Tiết kiệm/Tiền mặt**<br>**35% Vàng vật chất**<br>**35% Cổ phiếu VN30** | Hài hòa giữa tài sản phòng thủ và tài sản tăng trưởng. Danh mục có khả năng tự cân bằng qua các pha biến động của nền kinh tế. |
| **Tăng trưởng (Growth)** | $70 \le \text{Score} \le 100$ | $1.0 \le \lambda < 4.0$ | **20% Tiết kiệm/Tiền mặt**<br>**20% Vàng vật chất**<br>**60% Cổ phiếu VN30** | Tập trung khai thác đà tăng trưởng của thị trường cổ phiếu, duy trì tỷ lệ tiền gửi và vàng vừa đủ làm đệm thanh khoản và phòng vệ rủi ro vĩ mô. |

---

## 4. Tích hợp Phần mềm & Hợp đồng Dữ liệu (API Contract)

### 4.1. Lưu trữ Cơ sở Dữ liệu (PostgreSQL Schema)

Kết quả khảo sát được lưu trực tiếp vào bảng `users` và khởi tạo bản ghi trong bảng `portfolio_targets`:

```sql
-- Cập nhật vào hồ sơ người dùng
UPDATE users 
SET 
    risk_score = :calculated_score,
    risk_aversion_lambda = :calculated_lambda,
    risk_profile = :profile_enum -- 'CONSERVATIVE', 'BALANCED', 'GROWTH'
WHERE id = :user_id;

-- Khởi tạo tỷ trọng mục tiêu SAA mặc định (người dùng có thể tùy chỉnh sau)
INSERT INTO portfolio_targets (user_id, asset_class, target_weight) VALUES
(:user_id, 'CASH_SAVINGS', :weight_savings),
(:user_id, 'GOLD',         :weight_gold),
(:user_id, 'STOCK',        :weight_stock)
ON CONFLICT (user_id, asset_class) 
DO UPDATE SET target_weight = EXCLUDED.target_weight, updated_at = CURRENT_TIMESTAMP;
```

---

### 4.2. Đặc tả API Endpoint (JSON Interface)

#### Request: Nộp kết quả khảo sát
* **Endpoint:** `POST /api/v1/profile/risk-survey`
* **Xác thực:** Bearer Token (JWT)

```json
{
  "answers": [
    { "question_id": 1, "selected_option": "C", "score": 14 },
    { "question_id": 2, "selected_option": "C", "score": 14 },
    { "question_id": 3, "selected_option": "C", "score": 14 },
    { "question_id": 4, "selected_option": "C", "score": 14 },
    { "question_id": 5, "selected_option": "B", "score": 7 }
  ]
}
```

#### Response: Kết quả định lượng & Tỷ trọng đề xuất
* **HTTP Status:** `200 OK`

```json
{
  "status": "SUCCESS",
  "data": {
    "total_risk_score": 63,
    "risk_profile": "BALANCED",
    "risk_aversion_lambda": 4.33,
    "recommended_allocation": {
      "CASH_SAVINGS": 0.30,
      "GOLD": 0.35,
      "STOCK": 0.35
    },
    "profile_summary": "Hồ sơ của bạn thuộc nhóm Cân bằng. Bạn có năng lực tài chính ổn định và chấp nhận mức độ biến động vừa phải để tối ưu hóa tài sản trung và dài hạn."
  }
}
```

---

### 4.3. Cá nhân hóa Trợ lý Financial Copilot (Zero-Trust Context)

Dữ liệu khảo sát không chỉ dùng cho thuật toán toán học Markowitz mà còn được nạp làm **Ngữ cảnh Cố vấn (Advisory Context)** cho Copilot thông qua Spring AI:

1. **Bảo mật Zero-Trust:** Không truyền `userId` hay số dư chi tiết vào Prompt. Spring Security trích xuất `risk_profile` và `risk_aversion_lambda` trực tiếp từ Token đăng nhập.
2. **System Prompt Tiêm ngữ cảnh (Context Injection):**
   ```text
   Người dùng hiện tại thuộc nhóm hồ sơ: {risk_profile} (Hệ số ngại rủi ro λ = {risk_aversion_lambda}).
   - Khi giải thích kế hoạch tái cơ cấu, nếu người dùng là CONSERVATIVE, hãy nhấn mạnh vào tính an toàn vốn và bảo vệ lợi nhuận.
   - Nếu người dùng là GROWTH, hãy giải thích cơ hội gia tăng tài sản và lý do chấp nhận biến động ngắn hạn.
   - Luôn tuân thủ nguyên tắc Human-in-the-Loop: Khuyên người dùng tự kiểm tra lại trước khi thực hiện giao dịch ngoài thực tế.
   ```
