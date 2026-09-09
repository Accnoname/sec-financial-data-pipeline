# 🏛️ KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)
## SEC Financial Data Pipeline & RAG for US Stock Market

Dự án này là hệ thống Data Engineering kết hợp RAG (Retrieval-Augmented Generation) chuẩn công nghiệp thu nhỏ (phù hợp đồ án sinh viên và portfolio). Hệ thống tự động hóa việc thu thập, làm sạch, bóc tách và tạo vector embedding từ báo cáo tài chính thường niên (Form 10-K) của các công ty niêm yết tại Mỹ từ cổng thông tin **SEC EDGAR**.

---

## 1. Kiến Trúc Dữ Liệu Medallion (Data Lakehouse)

Dữ liệu được xử lý qua 4 tầng chất lượng tăng dần:

```
[SEC.gov EDGAR API]
        │
        ▼ (Bước 1, 3: Ingestion)
┌────────────────────────────────────────────────────────┐
│ 🟫 BRONZE LAYER (data/01_raw/)                         │
│  ├── companies/all_companies.json                      │
│  └── sec_filings/{TICKER}/*.htm (HTML gốc ~2-8 MB/file)│
└────────────────────────────────────────────────────────┘
        │
        ▼ (Bước 2, 4: Cleaning & Structuring)
┌────────────────────────────────────────────────────────┐
│ ⬜ SILVER LAYER (data/02_staging/)                     │
│  ├── companies_clean.parquet (Chuẩn hóa CIK 10 số)     │
│  └── sec_filings/{TICKER}/*_risk_factors.md            │
└────────────────────────────────────────────────────────┘
        │
        ▼ (Bước 5: Semantic Chunking & Metadata Enrichment)
┌────────────────────────────────────────────────────────┐
│ 🟨 GOLD LAYER (data/03_primary/)                       │
│  └── chunks/{TICKER}_{YEAR}_chunks.parquet             │
│      (Cắt đoạn 500 từ + overlap 100 từ + metadata)     │
└────────────────────────────────────────────────────────┘
        │
        ▼ (Embedding & Vector Storage)
┌────────────────────────────────────────────────────────┐
│ 🟩 CURATED / RAG LAYER (data/04_curated/)              │
│  └── vector_db/ (Qdrant / Chroma / FAISS Vector Store) │
└────────────────────────────────────────────────────────┘
```

---

## 2. Mô Tả Các Module Cốt Lõi (`src/`)

- **`src/common/`**:
  - `config.py`: Tự động nhận diện `PROJECT_ROOT`, nạp cấu hình `base_config.yaml`, cung cấp hằng số đường dẫn các tầng data.
  - `logger.py`: Centralized logger format chuẩn thời gian, module, cấp độ log.
- **`src/ingestion/`**:
  - `extract_companies.py`: Kéo danh mục ~10.400 công ty niêm yết từ SEC.gov API miễn phí.
  - `ingest_10k_filings.py`: Tự động tra cứu submission JSON và tải báo cáo 10-K mới nhất (GOOGL, AAPL, MSFT, NVDA,...).
- **`src/transformation/`**:
  - `clean_companies.py`: Làm sạch CIK chuẩn 10 số của SEC, deduplicate, nén Snappy Parquet (tiết kiệm ~76% dung lượng so với JSON).
  - `clean_10k_to_text.py`: Bóc tách DOM bằng BeautifulSoup, tước bỏ XBRL và CSS rác, trích xuất riêng `Item 1A. Risk Factors` ra Markdown.
- **`src/rag/`**:
  - `chunking.py`: Cắt văn bản thành semantic chunks kèm metadata (`chunk_id`, `ticker`, `year`, `section`) sẵn sàng nạp vào Vector DB.

---

## 3. Các Lệnh Chạy Chính

```bash
# Cài đặt thư viện
pip install -r requirements.txt

# Chạy giao diện menu chính
python run.py

# Hoặc chạy trực tiếp từng bước
python run.py 1    # Bước 1: Kéo danh mục công ty
python run.py 2    # Bước 2: Chuẩn hóa Parquet
python run.py 3    # Bước 3: Tải báo cáo 10-K
python run.py 4    # Bước 4: Bóc tách HTML sang Markdown
python run.py 5    # Bước 5: Cắt đoạn Chunking cho RAG
python run.py all  # Chạy tự động từ 1 đến 5

# Chạy Unit Test kiểm thử
pytest tests/ -v
```
