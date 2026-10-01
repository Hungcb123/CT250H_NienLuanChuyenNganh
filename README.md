# NIÊN LUẬN CHUYÊN NGÀNH KỸ THUẬT PHẦN MỀM (CT250H)

## ĐỀ TÀI: NỀN TẢNG THEO DÕI TÀI SẢN VÀ CỐ VẤN ĐẦU TƯ CÁ NHÂN (ROBO-ADVISOR & PORTFOLIO TRACKER)
### TÍCH HỢP SỔ CÁI KÉP, MÔ HÌNH DỰ BÁO HỌC MÁY VÀ TRỢ LÝ AI COPILOT

---

## 📌 HỆ THỐNG TÀI LIỆU THIẾT KẾ CỐT LÕI (3 BẢN MASTER SPECIFICATIONS)

Toàn bộ thiết kế hệ thống, giải thuật toán học và mô hình học máy được quy hoạch tập trung vào **3 tài liệu chuẩn mực**:

| STT | Tài liệu | Mô tả & Công năng | Liên kết truy cập |
| :---: | :--- | :--- | :---: |
| **1** | **Master SRS (Bản Đặc tả Toàn diện)** | Đặc tả toàn bộ yêu cầu phần mềm, kiến trúc hệ thống (Java 21, Spring Boot 3, PostgreSQL 16 + pgvector), luồng người dùng 6 giai đoạn, lõi Sổ cái kép (ACID Invariants, Lãi kép tự động), bộ giải toán Markowitz MVO & quy đổi lô chẵn 100 cp, DDL CSDL và kiểm toán Spring Batch. | 📄 [SRS.md](file:///mnt/d/Project_CT250H_NienLuanChuyenNganh/SRS.md) |
| **2** | **Đặc tả Mô hình Học máy (Machine Learning)** | Phân tích toàn diện các mô hình máy học ứng viên (Logistic Regression, Random Forest, XGBoost, LightGBM, Bi-LSTM), kỹ nghệ 30+ đặc trưng kỹ thuật, chiến lược gắn nhãn chu kỳ $T+20$, kiểm thử Walk-Forward chống Data Leakage, tối ưu Optuna, đóng gói chuẩn ONNX và nhúng suy luận trực tiếp trong RAM JVM $< 3\text{ ms}$. | 📄 [dac_ta_mo_hinh_may_hoc.md](file:///mnt/d/Project_CT250H_NienLuanChuyenNganh/dac_ta_mo_hinh_may_hoc.md) |
| **3** | **Đặc tả Bộ Câu hỏi Khảo sát Khẩu vị Rủi ro** | Chi tiết bộ 5 câu hỏi chuẩn hóa (thang điểm 100), công năng và bản chất tài chính từng câu, mô hình hóa toán học ánh xạ sang Hệ số ngại rủi ro $\lambda \in [1.0, 10.0]$ và Ma trận Tỷ trọng Chiến lược Neo ban đầu (SAA Baseline), hợp đồng API JSON và schema CSDL. | 📄 [bo_cau_hoi_khao_sat_khau_vi_rui_ro.md](file:///mnt/d/Project_CT250H_NienLuanChuyenNganh/bo_cau_hoi_khao_sat_khau_vi_rui_ro.md) |

---

## 🛠️ CÔNG NGHỆ CHỦ ĐẠO
* **Backend:** Java 21 (LTS), Spring Boot 3.3+, Spring Data JPA, Spring Security, Spring Batch, Spring AI.
* **Database & Vector Search:** PostgreSQL 16 kết hợp extension `pgvector` (HNSW Index) và Full-Text Search (GIN Index) thực thi Hybrid Search qua RRF CTE thuần trong CSDL.
* **Machine Learning Inference:** Embedded Microsoft ONNX Runtime (`com.microsoft.onnxruntime`) chạy trực tiếp trong bộ nhớ JVM (Zero Python at Runtime).
* **Kiến trúc:** Modular Monolith theo phong cách Hexagonal (Ports & Adapters).
