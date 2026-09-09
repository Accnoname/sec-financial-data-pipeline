# 📓 SEC FINANCIAL PIPELINE — PROJECT LEARNING JOURNAL
> **Áp dụng bộ Skill: `how_to_learn_form_project` vào dự án thực tế**

---

## 1. PROJECT OVERVIEW (SKILL 01)
- **Tên Dự Án**: SEC Financial Data Pipeline & AI RAG System
- **Bài toán giải quyết**: Tự động hóa việc thu thập, làm sạch, bóc tách phần rủi ro kinh doanh (Item 1A Risk Factors) từ báo cáo tài chính Form 10-K của các tập đoàn công nghệ lớn trên SEC EDGAR để phục vụ hỏi đáp AI.
- **Input**: 
  - SEC EDGAR API JSON (`company_tickers_exchange.json`)
  - SEC EDGAR Submissions API & HTML 10-K gốc (~2-8 MB/file)
- **Output**:
  - `companies_clean.parquet` (Silver)
  - `*_risk_factors.md` (Silver Markdown sạch thẻ rác)
  - `*_chunks.parquet` & `all_chunks.parquet` (Gold - 262 semantic chunks kèm metadata)
  - Vector DB & RAG Retrieval Interface (Curated)
- **Success Metrics**:
  - Tự động hóa 100% không thao tác thủ công.
  - Tiết kiệm >75% dung lượng qua định dạng Parquet Snappy.
  - Trích xuất chuẩn xác >10.000 ký tự Item 1A cho 100% các công ty mục tiêu.
  - 100% test suite `pytest` vượt qua.

---

## 2. KIẾN TRÚC MEDALLION & DATA CONTRACTS
```text
[SEC EDGAR API]
       │
       ▼
[01_raw (Bronze)]
  - companies/all_companies.json
  - sec_filings/{TICKER}/*.htm
       │
       ▼
[02_staging (Silver)]
  - companies_clean.parquet (CIK 10 số)
  - sec_filings/{TICKER}/*_risk_factors.md
       │
       ▼
[03_primary (Gold)]
  - chunks/*_chunks.parquet & all_chunks.parquet (500 từ + overlap 100 từ)
       │
       ▼
[04_curated (RAG)]
  - Vector Store (Qdrant / Chroma / Embeddings)
```

---

## 3. CHECKPOINTS CÁC BƯỚC ĐÃ TRIỂN KHAI (SKILL 06 & 07)

### ✅ Checkpoint Bước 1 & 2: Danh Mục Công Ty & Chuẩn Hóa CIK
1. **Đã xây dựng**: Pipeline kéo 10.407 công ty từ SEC và chuẩn hóa sang Parquet.
2. **Kiến thức cốt lõi**: `requests`, `pandas` (`drop_duplicates`, `zfill(10)`, `to_parquet` engine `pyarrow` compression `snappy`).
3. **Quyết định kỹ thuật (Skill 09)**: Dùng Parquet Snappy thay vì CSV/JSON để tối ưu tốc độ đọc theo cột và giảm 76% dung lượng đĩa.
4. **Explain Without Code**: "Kéo dữ liệu JSON từ SEC, lọc bỏ bản ghi thiếu thông tin, đưa mã CIK về chuẩn 10 số bằng cách thêm số 0 vào đầu, loại bỏ mã cổ phiếu trùng và lưu thành file Parquet nhị phân nén nhanh."

### ✅ Checkpoint Bước 3 & 4: Ingestion 10-K & Bóc Tách HTML sang Markdown
1. **Đã xây dựng**: Tự động tải file 10-K gốc của 7 tập đoàn (AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA) và bóc tách `Item 1A. Risk Factors` ra file Markdown.
2. **Kiến thức cốt lõi**: DOM traversal bằng BeautifulSoup (`lxml`), tước bỏ thẻ `script`, `style`, `ix:header`, biểu thức chính quy RegEx (`ITEM_1A_PATTERN`, `NEXT_ITEM_PATTERN`).
3. **Bài học sửa lỗi (Skill 08)**: 
   - *Lỗi*: Microsoft (MSFT) không khớp được tiêu đề `ITEM 1A. RISK FACTORS`.
   - *Nguyên nhân*: File HTML của MSFT bị ngắt thẻ mềm giữa chữ `RIS` và `K` (`RIS\nK FACTORS`).
   - *Quy tắc tổng quát*: Khi xử lý HTML từ báo cáo tài chính thực tế, không bao giờ giả định văn bản liền mạch; luôn cho phép khoảng trắng hoặc ký tự ngắt dòng tùy chọn giữa các ký tự tiêu đề.

### ✅ Checkpoint Bước 5: Semantic Chunking (Tầng Gold)
1. **Đã xây dựng**: Cắt văn bản thành các chunks 500 từ, gối đầu 100 từ kèm metadata phong phú (`chunk_id`, `ticker`, `year`, `section`, `word_count`).
2. **Kết quả**: 262 chunks trên toàn bộ 7 công ty được lưu tại `data/03_primary/chunks/all_chunks.parquet`.

---

## 4. KẾ HOẠCH BƯỚC TIẾP THEO: V1 ➔ V2 & TẦNG CURATED (SKILL 11)
- **Điểm yếu hiện tại**: Dữ liệu Gold mới dừng ở dạng file Parquet, chưa có khả năng tìm kiếm ngữ nghĩa theo câu hỏi tự nhiên.
- **Mục tiêu V2**: Xây dựng Tầng 4 (Curated) tích hợp Vector Store & Module RAG Search để so sánh rủi ro giữa các công ty (ví dụ: So sánh rủi ro AI giữa Nvidia và Google).
