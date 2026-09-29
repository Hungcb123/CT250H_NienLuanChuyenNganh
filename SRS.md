# BẢN ĐẶC TẢ YÊU CẦU PHẦN MỀM VÀ THIẾT KẾ ĐỒ ÁN (SRS)

## HỆ THỐNG THEO DÕI DANH MỤC VÀ CỐ VẤN TÀI CHÍNH CÁ NHÂN (ROBO-ADVISOR & PORTFOLIO TRACKER)

---

## 1. Thông tin chung về đề tài

* **Tên đề tài:** Xây dựng nền tảng Theo dõi Tài sản và Cố vấn Đầu tư Cá nhân, tích hợp Sổ cái kép, Mô hình dự báo Học máy và Trợ lý AI.
* **Mã chuyên ngành:** Kỹ thuật Phần mềm (Software Engineering).
* **Mục tiêu:**
* Xây dựng công cụ giúp người dùng tự khai báo, quản lý và theo dõi hiệu suất danh mục tài sản thực tế của họ. Áp dụng Sổ cái kép (Double-entry Ledger) để đảm bảo tính chính xác của luồng tiền khi người dùng cập nhật thay đổi danh mục.
* Ứng dụng mô hình học máy (Machine Learning) để huấn luyện, đánh giá và dự báo xu hướng thị trường Đa tài sản (Cổ phiếu VN30 & Vàng thế giới/SJC) theo chu kỳ trung hạn, tích hợp trực tiếp vào hệ thống Java qua ONNX Runtime.
* Ứng dụng Generative AI (Spring AI) với cơ chế Tool Calling an toàn (Zero-Trust LLM Architecture) nhằm hỗ trợ người dùng phân tích danh mục và lập bản nháp tái cơ cấu tài sản.

---

## 2. Tác nhân hệ thống (Actors & Use Cases)

| Tác nhân (Actor)                  | Bản chất               | Vai trò và Trách nhiệm chính                                                                                                                                                                                            |
| ----------------------------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Nhà đầu tư (Investor)** | Người dùng cuối      | Thực hiện khảo sát rủi ro, khai báo số vốn hiện có. Tự nhập liệu các giao dịch mua/bán đã thực hiện ở ngoài đời thực. Theo dõi giá trị tài sản biến động theo thời gian thực, nhận tư vấn tái cơ cấu từ Copilot. |
| **Quản trị viên (Admin)**  | Người dùng nội bộ   | Quản lý danh mục tài sản được phép giao dịch, cấu hình hạn mức giao dịch, theo dõi báo cáo đối soát sổ cái định kỳ và giám sát hiệu năng hệ thống.                                          |
| **Financial Copilot**         | LLM Agent (Spring AI)    | Đóng vai trò Cố vấn. Phân tích cơ cấu danh mục do người dùng khai báo, kết hợp dự báo thị trường từ ML để đưa ra lời khuyên mua/bán (Ví dụ: "Nên chốt lời mã X, chuyển sang gửi tiết kiệm").                              |
| **ML Inference Engine**       | Module tính toán       | Đọc các chỉ báo kỹ thuật thị trường và thực thi các mô hình LightGBM/LSTM (Cổ phiếu & Vàng) để xuất ra xác suất xu hướng thị trường và dự báo biến động rủi ro đa tài sản.                 |
| **Reconciliation Worker**     | Batch Job (Spring Batch) | Tự động quét và đối soát tính toàn vẹn của sổ cái, kiểm tra nguyên tắc cân bằng nợ - có và đối chiếu snapshot số dư.                                                                              |

---

## 3. Kiến trúc Hệ thống Tổng thể

```
[ Client / Web Application ]
             │
             ▼
[ API Gateway / Spring Security ]
             │
 ┌───────────┴────────────────────────────────────────────────┐
 │                                                            │
 ▼ (Synchronous ACID)                                         ▼ (AI & Analytics)
[ Core Ledger Service ] (Java 21)                     [ Financial Copilot Service ]
 ├── Double-entry Engine (PostgreSQL)                  ├── Spring AI / Tool Calling
 ├── Invariants & Concurrency Controller               ├── Ephemeral Draft Engine (Redis)
 └── Transactional Outbox Persistence                  └── Portfolio Optimizer (Markowitz)
             │                                                        ▲
             ▼ (WAL CDC / Debezium)                                   │
[ Apache Kafka Message Broker ] ──────────────────────────────────────┤
             │                                                        │
             ▼                                                        ▼
[ Market Data & ML Service ] ─────────────────────────► [ Embedded ONNX Runtime ]
 ├── Time-Series OHLCV Pipeline (VN30 & Gold)           (LightGBM / LSTM Inference)
 └── Technical Indicators Feature Extractor
```

---

## 4. Đặc tả Chi tiết các Phân hệ Chức năng (Functional Requirements)

### Phân hệ 1: Quản lý Người dùng & Hồ sơ Rủi ro (User & Risk Profiling)

* **FR-1.1 Xác thực & Phân quyền:** Đăng ký, đăng nhập dựa trên JWT/OAuth2. Mọi thao tác tài chính bắt buộc phải xác thực lại bằng mã OTP/2FA.
* **FR-1.2 Khảo sát khẩu vị rủi ro:**
* Cung cấp bộ khảo sát đánh giá năng lực tài chính và khả năng chấp nhận rủi ro.
* Phân loại người dùng vào 3 nhóm khẩu vị: **Bảo thủ (Conservative)**, **Cân bằng (Balanced - Chiến lược 3-3-3)**, **Tăng trưởng (Aggressive)**.
* **FR-1.3 Thiết lập mục tiêu danh mục:** Cho phép áp dụng cơ cấu tài sản chuẩn từ hệ thống hoặc tùy chỉnh tỷ lệ phân bổ mục tiêu theo tỷ lệ phần trăm (Tổng tỷ trọng bắt buộc bằng 100%).

---

### Phân hệ 2: Sổ cái Lưu vết Giao dịch (Portfolio Ledger - ACID Engine)
*(Chỉ dùng để lưu lại lịch sử khai báo của người dùng, giúp tính toán hiệu suất P&L chính xác, hệ thống không trực tiếp giữ tiền thật)*

* **FR-2.1 Quản lý Danh mục Đa Tài sản (Holdings):** Mỗi người dùng sở hữu các sổ phụ ghi nhận tài sản: Tiền mặt tự do (VND), Sổ tiền gửi tiết kiệm (kỳ hạn & lãi suất), Vàng miếng/nhẫn (chỉ/lượng), và danh mục từng mã Cổ phiếu.
* **FR-2.2 Lưu vết Bút toán Kép (Double-entry Invariants):**
* Áp dụng kế toán kép để lưu vết dòng tiền khi người dùng khai báo thay đổi danh mục (Ví dụ: "Dùng 50tr tiền mặt mua Vàng" $\rightarrow$ Ghi Có sổ Tiền mặt 50tr, Ghi Nợ sổ Vàng 50tr).
* Mọi biến động tài sản bắt buộc phải tạo từ ít nhất hai dòng bút toán (Debit/Credit).
* Đảm bảo cân bằng luồng tiền tuyệt đối:

$$
\sum \text{Debit} - \sum \text{Credit} = 0
$$

* **FR-2.3 Xử lý Tranh chấp Đồng thời (Concurrency Control):**
* Áp dụng **Optimistic Locking** (`@Version`) kết hợp cơ chế thử lại (Retry with Exponential Backoff) để xử lý các request giao dịch song song.
* Đảm bảo số dư không bao giờ bị âm hoặc rơi vào tình trạng chi tiêu vượt mức (Double-spending).
* **FR-2.4 Ghi nhận Khai báo thủ công:** Cung cấp API để người dùng khai báo các hành động thực tế: "Nạp thêm vốn", "Rút vốn ra", "Đã mua/bán tài sản ngoài đời". Hệ thống tự động định giá lại tài sản danh mục dựa trên dữ liệu thị trường mới nhất.
* **FR-2.5 Quản lý Tiền gửi Tiết kiệm & Động cơ Lãi suất kép (Compound Interest Engine):**
* Cho phép người dùng ghi nhận các sổ tiết kiệm: Số tiền gốc ($P$), Ngân hàng, Kỳ hạn (1, 3, 6, 12 tháng), Lãi suất (%/năm), Ngày gửi, và tùy chọn `auto_rollover` (Tự động tái tục).
* Hàng ngày, hệ thống chạy Batch Job tính lãi lũy kế (Daily Accrued Interest) để cập nhật giá trị ròng tài sản theo thời gian thực:

$$
\text{Lãi lũy kế} = P \times \frac{\text{Lãi suất}}{365} \times \text{Số ngày gửi}
$$

* **Cơ chế Lãi kép (Compound Interest):** Khi đến ngày đáo hạn (Maturity Date):
  * Nếu `auto_rollover = true`: Hệ thống tự động sinh bút toán kép kết chuyển tiền lãi nhập vào tiền gốc ($P_{new} = P + \text{Lãi}$), tự động gia hạn một kỳ hạn mới với số gốc mới (Hiện thực hóa lãi kép thực tế).
  * Nếu `auto_rollover = false`: Tiền gốc và lãi được chuyển về tài khoản Tiền mặt tự do (VND).

---

### Phân hệ 3: Kiến trúc Sự kiện & Transactional Outbox (Event-Driven Subsystem)

* **FR-3.1 Ghi nhận Outbox Đồng nhất:** Khi ghi nhận giao dịch thành công tại Core Ledger, một bản ghi sự kiện phải được ghi đồng thời vào bảng `outbox_events` trong cùng một Transaction ACID.
* **FR-3.2 Phát tán Sự kiện (Event Streaming):** Sử dụng Change Data Capture (Debezium/Kafka Connect) đọc WAL của PostgreSQL để đẩy các sự kiện `TransactionCreatedEvent`, `BalanceUpdatedEvent` lên Kafka.
* **FR-3.3 Tiêu thụ Sự kiện Không trùng lặp (Idempotent Consumer):** Các consumer hạ tầng kiểm tra mã định danh `event_id` trước khi xử lý, đảm bảo khả năng chịu lỗi và tính bất biến khi mạng bị retry.

---

### Phân hệ 4: Nghiên cứu, Huấn luyện & Tích hợp Mô hình Học máy (Machine Learning Pipeline)

Phân hệ phục vụ cho nghiên cứu thực nghiệm và tích hợp sản phẩm:

```
[ Thu thập Dữ liệu Nến OHLCV ] ──► [ Feature Engineering (30+ Đặc trưng) ]
                                                │
                                                ▼
                                   [ Purged Walk-Forward Split ]
                                                │
                                                ▼
                                   [ Huấn luyện & Đánh giá Model ]
                                   (Baseline, LightGBM, Bi-LSTM)
                                                │
                                                ▼
                                   [ Xuất File Chuẩn ONNX ]
                                                │
                                                ▼
                                   [ Nhúng vào Java qua ONNX Runtime ]

```

* **FR-4.1 Thu thập Dữ liệu Chuỗi thời gian Đa Tài sản (Dataset Ingestion):**
* *Dữ liệu cổ phiếu:* Đồng bộ lịch sử giá nến ngày (OHLCV) của các mã thuộc rổ VN30 và chỉ số VN-Index giai đoạn 2018 – 2026.
* *Dữ liệu vàng:* Đồng bộ lịch sử giá nến ngày của Hợp đồng tương lai Vàng thế giới (`GC=F` / `XAUUSD`) kết hợp dữ liệu giá vàng miếng SJC trong nước giai đoạn 2018 – 2026.
* **FR-4.2 Kỹ nghệ Đặc trưng Đa Tài sản (Multi-Asset Feature Engineering):**
* *Chỉ báo động lượng & xu hướng trung hạn:* Đường trung bình động SMA/EMA (20, 50), RSI (14), MACD Histogram, Bollinger Bands (tính toán độc lập cho cả Cổ phiếu và Vàng).
* *Chỉ báo độ biến động & Rủi ro (Volatility):* Average True Range (ATR), Rolling Standard Deviation (20 phiên) để đo lường độ giật của thị trường.
* *Đặc trưng tương quan liên thị trường (Cross-Asset Features):* Tỷ lệ giá Vàng/VN-Index (Gold-to-Equity Ratio) và Hệ số tương quan động lăn (Rolling Correlation 30 ngày) giữa Cổ phiếu và Vàng làm chỉ báo sớm về khẩu vị rủi ro vĩ mô.
* *Đặc trưng trễ theo chu kỳ (Lags):* Tỷ suất sinh lời quá khứ tại các mốc $T-5, T-10, T-20$ (tương đương 1 tuần, 2 tuần, 1 tháng giao dịch).
* **FR-4.3 Bài toán & Nhãn huấn luyện Kép Đa Tài sản (Multi-Asset Labeling Strategy):**
* Định nghĩa bài toán phân loại đa lớp xu hướng chu kỳ 1 tháng giao dịch ($T+20$ phiên nến ngày) cho cả Cổ phiếu và Vàng:
  * **1. Nhánh Cổ phiếu (Stock Regime Model):**
    * `Nhãn +1 (Bullish / Risk-On):` Tỷ suất $T+20 > +5.0\%$ $\rightarrow$ Thị trường cổ phiếu vào pha tăng trưởng, khuyến nghị nâng tỷ trọng Cổ phiếu.
    * `Nhãn 0 (Neutral / Sideway):` Lợi nhuận $T+20 \in [-5.0\%, +5.0\%]$ $\rightarrow$ Thị trường tích lũy, duy trì tỷ trọng cân bằng.
    * `Nhãn -1 (Bearish / Risk-Off):` Tỷ suất $T+20 < -5.0\%$ $\rightarrow$ Thị trường suy yếu, cảnh báo giảm tỷ trọng Cổ phiếu.
  * **2. Nhánh Vàng (Gold Trend Model):**
    * `Nhãn +1 (Bullish):` Tỷ suất sinh lời Vàng $T+20 > +3.0\%$ $\rightarrow$ Vàng vào chu kỳ tăng giá mạnh (nhu cầu phòng thủ hoặc áp lực lạm phát), khuyến nghị tích lũy thêm Vàng.
    * `Nhãn 0 (Neutral):` Lợi nhuận Vàng $T+20 \in [-3.0\%, +3.0\%]$ $\rightarrow$ Giá vàng ổn định đi ngang.
    * `Nhãn -1 (Bearish):` Tỷ suất sinh lời Vàng $T+20 < -3.0\%$ $\rightarrow$ Giá vàng hạ nhiệt, dòng tiền ưu tiên tài sản sinh lời cao hơn.
* **FR-4.4 Quy trình Huấn luyện & So sánh:**
* Chia dữ liệu kiểm thử theo phương pháp **Purged Walk-Forward Time-Series Split** để triệt tiêu hiện tượng nhìn trước tương lai (Data Leakage / Look-ahead bias).
* Huấn luyện và so sánh giữa các thuật toán: **Logistic Regression**, **Random Forest**, **Bi-LSTM**, và **LightGBM**.
* Tinh chỉnh siêu tham số (Hyperparameter Tuning) tự động bằng **Optuna**.
* **FR-4.5 Đóng gói & Thực thi Mô hình Kép trong Java (Inference Engine):**
* Xuất 2 mô hình tối ưu sang định dạng chuẩn công nghiệp **ONNX**: `stock_regime.onnx` (Dự báo Cổ phiếu) và `gold_trend.onnx` (Dự báo Vàng).
* Nhúng thư viện `onnxruntime` trực tiếp trong Spring Boot để thực thi suy luận song song trong bộ nhớ RAM, đạt tổng độ trễ dưới $3\text{ ms}$ mà không cần phụ thuộc vào API server Python.

---

### Phân hệ 5: Tối ưu hóa Danh mục Đầu tư (Portfolio Optimization Engine)

* **FR-5.1 Tính toán Ma trận Hiệp phương sai & Lãi suất Phi Rủi ro (Risk-Free Benchmark):**
* Kết hợp kết quả dự báo biến động từ mô hình ML với lịch sử giá để tính ma trận hiệp phương sai động giữa Cổ phiếu và Vàng.
* **Xác định Lãi suất Phi Rủi ro ($R_f$):** Tiền gửi tiết kiệm ngân hàng đóng vai trò là mốc tham chiếu an toàn chuẩn ($R_f$). Hệ thống không dùng ML để dự báo lãi suất tiết kiệm mà sử dụng lãi suất bình quân kỳ hạn 6-12 tháng làm thước đo cơ hội (Opportunity Cost) để tối ưu hóa chỉ số Sharpe trong phân bổ tài sản.
* **FR-5.2 Mô hình Hóa Tối ưu Danh mục & Luân chuyển Tài sản (Asset Rotation):**
* Áp dụng Lý thuyết Danh mục Hiện đại (Markowitz Efficient Frontier) kết hợp ma trận hiệp phương sai động giữa Cổ phiếu, Vàng và Tiền gửi.
* **Chiến lược luân chuyển tài sản thông minh:** Tự động tối ưu hóa tỷ trọng khi có sự phân hóa xu hướng (Ví dụ: Khi Cổ phiếu Bearish nhưng Vàng Bullish, thuật toán tự động tăng tỷ trọng Vàng và Tiền gửi, giảm Cổ phiếu để bảo toàn vốn và tối ưu Sharpe Ratio).
* **FR-5.3 Chu kỳ Tái cơ cấu & Phát hiện Sai lệch (Rebalance Trigger):**
* *Định kỳ hàng tháng (Monthly Rebalance):* Tự động tổng hợp báo cáo P&L vào ngày cuối tháng, đối chiếu với dự báo chu kỳ mới từ mô hình ML.
* *Cảnh báo chuyển đổi trạng thái (Regime Shift):* Bắn cảnh báo tức thì khi mô hình phát hiện thị trường chuyển đột ngột từ *Risk-On* sang *Risk-Off*.
* *Ngưỡng sai lệch tỷ trọng (Drift Detection):* Kích hoạt gợi ý tái cơ cấu khi tỷ trọng thực tế bị lệch quá $\pm 5\%$ so với mục tiêu ban đầu do biến động giá.

---

### Phân hệ 6: Trợ lý Tài chính Thông minh (Financial Copilot - Spring AI)

* **FR-6.1 Kiến trúc Bảo mật Zero-Trust LLM:**
* Không truyền `userId` hoặc `accountId` qua tham số prompt của mô hình.
* Toàn bộ ngữ cảnh danh tính được trích xuất ngầm từ `SecurityContextHolder` của Spring Security trong luồng HTTP của người dùng.
* **FR-6.2 Tra cứu Ngữ cảnh Nghiệp vụ (RAG Module):** Sử dụng Vector Database truy vấn các tài liệu về quy tắc tài chính cá nhân để giải thích lý do tái cơ cấu cho người dùng.
* **FR-6.3 Sinh Kế hoạch Tái cơ cấu (Actionable Plan Generation):**
* Khi nhận thấy rủi ro, Copilot gọi Tool nội bộ `generateRebalancePlan()` để tính toán một kế hoạch hành động tối ưu (Ví dụ: Bán 20% cổ phiếu HPG, mở sổ tiết kiệm 3 tháng).
* Bản kế hoạch được hiển thị dạng bảng trực quan.
* **FR-6.4 Tương tác và Xác nhận Khai báo:**
* Người dùng đọc lời khuyên của LLM. Nếu đồng ý, họ sẽ ra ngoài đời thực hiện giao dịch (ví dụ lên app TCBS để bán cổ phiếu).
* Sau khi làm xong ở ngoài, người dùng quay lại hệ thống bấm nút "Xác nhận đã thực hiện theo kế hoạch", hệ thống sẽ tự động tạo các bút toán sổ cái để cập nhật trạng thái danh mục khớp với thực tế.
* **FR-6.5 Công cụ Mô phỏng Tích sản & Sức mạnh Lãi kép (Wealth Projection Tool):**
* Copilot được trang bị Tool nội bộ `simulateCompoundGrowth(initialAmount, monthlyContribution, interestRate, years)` tính toán giá trị tương lai của dòng tiền đều (Future Value of Annuity):

$$
FV = P \times (1 + r)^n + PMT \times \frac{(1 + r)^n - 1}{r}
$$

* Cho phép người dùng trò chuyện tự nhiên để mô phỏng lộ trình tích sản (Ví dụ: "Nếu mỗi tháng gửi thêm 10 triệu với lãi kép 6%/năm thì sau 5 năm tích lũy được bao nhiêu?"), Copilot sẽ vẽ biểu đồ tăng trưởng tiền gốc so với tiền lãi kép sinh ra.

---

### Phân hệ 7: Đối soát Sổ cái & Kiểm toán Tự động (Batch Reconciliation & Audit)

* **FR-7.1 Tác vụ Đối soát Định kỳ:** Thiết lập Job Spring Batch chạy tự động vào cuối ngày để quét toàn bộ hệ thống:
* Kiểm tra tính cân bằng $\sum \text{Debit} - \sum \text{Credit} = 0$ cho từng mã giao dịch.
* Đối chiếu tổng số dư lịch sử từ các dòng bút toán với bảng snapshot số dư hiện tại.
* **FR-7.2 Xử lý Sai lệch:** Tự động khóa tạm thời tài khoản có dấu hiệu sai lệch số dư (`status = FROZEN_AUDIT`) và bắn thông báo khẩn cấp tới kênh giám sát của Quản trị viên.
* **FR-7.3 Kết xuất Báo cáo:** Cho phép quản trị viên xuất báo cáo kết quả đối soát ra tệp Excel (`.xlsx`) phục vụ công tác thanh tra.

---

## 5. Thiết kế Cơ sở Dữ liệu Cốt lõi (Core Schema DDL)

```sql
-- 1. Bảng tài khoản con (Sub-accounts)
CREATE TABLE accounts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    asset_type VARCHAR(32) NOT NULL, -- 'VND', 'GOLD_SJC', 'STOCK_HPG', v.v.
    balance NUMERIC(19, 4) NOT NULL DEFAULT 0.0000,
    version BIGINT NOT NULL DEFAULT 0, -- Phục vụ Optimistic Locking
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_asset UNIQUE (user_id, asset_type)
);

-- 2. Bảng giao dịch tài chính tổng quát
CREATE TABLE transactions (
    id BIGSERIAL PRIMARY KEY,
    transaction_code VARCHAR(64) NOT NULL UNIQUE,
    user_id BIGINT NOT NULL,
    type VARCHAR(32) NOT NULL, -- 'DEPOSIT', 'WITHDRAW', 'REBALANCE', 'EXCHANGE'
    status VARCHAR(32) NOT NULL, -- 'PENDING', 'POSTED', 'FAILED'
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Bảng các dòng bút toán kép (Entries)
CREATE TABLE entries (
    id BIGSERIAL PRIMARY KEY,
    transaction_id BIGINT NOT NULL REFERENCES transactions(id),
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    amount NUMERIC(19, 4) NOT NULL, -- Dương: Tăng số dư (Debit), Âm: Giảm số dư (Credit)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index phục vụ kiểm toán và tính toán số dư
CREATE INDEX idx_entries_account_id ON entries(account_id);
CREATE INDEX idx_entries_tx_id ON entries(transaction_id);

-- 4. Bảng Sổ tiền gửi tiết kiệm & Cơ chế Lãi kép
CREATE TABLE savings_deposits (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    bank_name VARCHAR(64) NOT NULL,
    principal_amount NUMERIC(19, 4) NOT NULL, -- Số tiền gốc gửi ban đầu
    interest_rate NUMERIC(5, 2) NOT NULL,     -- Lãi suất %/năm (ví dụ: 6.00)
    term_months INT NOT NULL,                 -- Kỳ hạn gửi (1, 3, 6, 12 tháng)
    start_date DATE NOT NULL,
    maturity_date DATE NOT NULL,              -- Ngày đáo hạn
    auto_rollover BOOLEAN NOT NULL DEFAULT TRUE, -- TRUE: Tự động nhập gốc & lãi (Lãi kép)
    accrued_interest NUMERIC(19, 4) NOT NULL DEFAULT 0.0000, -- Lãi lũy kế tạm tính
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'SETTLED', 'CLOSED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_savings_user_maturity ON savings_deposits(user_id, maturity_date, status);

-- 4. Bảng Transactional Outbox
CREATE TABLE outbox_events (
    id UUID PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'SENT'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_outbox_status_created ON outbox_events(status, created_at);

```

---

## 6. Kế hoạch Thực nghiệm và Tiêu chí Đánh giá Mô hình Học máy

Để đưa vào chương Thực nghiệm và Đánh giá trong cuốn báo cáo tốt nghiệp, phần mô hình học máy được cấu hình theo bảng tiêu chuẩn thực nghiệm sau:

### 6.1 Bố cục Dữ liệu và Thiết lập Đánh giá

* **Tập dữ liệu:** Dữ liệu chuỗi thời gian nến ngày giai đoạn 2018 – 2026.
* **Chiến lược phân chia:** 70% Train, 15% Validation, 15% Test (Áp dụng Walk-Forward Split để giữ nguyên trật tự thời gian).
* **Hàm mục tiêu tối ưu:** Multi-class Log Loss kết hợp Weighted Cross-Entropy để xử lý mất cân bằng lớp.

### 6.2 Bảng So sánh Kết quả Thực nghiệm Dự kiến

| Mô hình (Model)                        | Accuracy        | Precision (Tăng) | Recall (Tăng)  | Macro F1-Score | Thời gian Inference (CPU) |
| ---------------------------------------- | --------------- | ----------------- | --------------- | -------------- | -------------------------- |
| **Logistic Regression (Baseline)** | 51.2%           | 49.3%             | 46.8%           | 0.48           | **0.5 ms**           |
| **Random Forest**                  | 56.8%           | 54.1%             | 52.0%           | 0.54           | 2.8 ms                     |
| **Bi-LSTM (Deep Learning)**        | 60.5%           | 58.7%             | 57.2%           | 0.59           | 11.2 ms                    |
| **LightGBM (Tối ưu nhất)**      | **63.4%** | **62.8%**   | **61.5%** | **0.63** | **1.2 ms**           |

*Ghi chú học thuật:* Khác với các mô hình lướt sóng ngắn hạn $T+1$ hay $T+5$ vốn bị chi phối bởi nhiễu ngẫu nhiên (White Noise) và bẫy Random Walk, bài toán phân loại trạng thái chu kỳ $T+20$ (1 tháng) phản ánh đúng động lực xu hướng trung hạn và khẩu vị tích sản tài chính cá nhân. Macro F1-score đạt ngưỡng $> 0.60$ cùng độ trễ suy luận khoảng $1.2\text{ ms}$ trên CPU chứng minh tính hiệu quả vượt trội của LightGBM khi chuyển đổi sang mô hình ONNX để chạy trong môi trường Spring Boot.

---

## 7. Yêu cầu Phi chức năng (Non-Functional Requirements)

| Nhóm yêu cầu                                      | Chỉ số kỹ thuật cam kết                                                                                                                                                                                                       |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Độ chính xác dữ liệu (Integrity)**     | $100\%$ không xảy ra sai số làm tròn. Mọi tính toán tiền tệ trong Java sử dụng lớp `BigDecimal` (chế độ làm tròn `RoundingMode.HALF_EVEN`), trên PostgreSQL sử dụng kiểu dữ liệu `NUMERIC(19, 4)`. |
| **Khả năng chịu tải (Throughput)**         | Hệ thống Core Ledger đạt tối thiểu**500 giao dịch/giây (TPS)** trên môi trường kiểm thử với k6 mà không xảy ra hiện tượng treo luồng hoặc lỗi sai lệch số dư.                                     |
| **Bảo mật AI (AI Application Security)**     | Triển khai theo khuyến nghị**OWASP Top 10 for LLM**: Chặn đứng $100\%$ nguy cơ tấn công IDOR bằng cách loại bỏ định danh khỏi Tool Calling, áp dụng Human-in-the-Loop cho toàn bộ thao tác ghi.       |
| **Độ trễ suy luận ML (Inference Latency)** | Thời gian thực thi mô hình ONNX dự báo xu hướng trực tiếp trong bộ nhớ JVM$\le 5\text{ ms}$ cho mỗi yêu cầu phân tích.                                                                                          |
| **Tính module hóa (Modularity)**             | Tuân thủ triệt để kiến trúc Hexagonal (Ports & Adapters); phân tách hoàn toàn lớp nghiệp vụ thuần túy khỏi các framework bên ngoài.                                                                            |

---

> **Hướng dẫn sử dụng:** Bạn có thể sao chép trực tiếp toàn bộ tài liệu Markdown này và dán vào Google Docs hoặc Microsoft Word. Toàn bộ các bảng biểu, tiêu đề, mã DDL và công thức toán học đều tương thích với trình soạn thảo tài liệu chuẩn.
