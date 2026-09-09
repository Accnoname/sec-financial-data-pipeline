# 📈 SEC Financial Data Pipeline & RAG System
> **Hệ thống Xử Lý Dữ Liệu Tài Chính & AI RAG (Retrieval-Augmented Generation) từ Báo Cáo 10-K SEC EDGAR**  
> *Đồ án / Portfolio chuẩn Data Engineering & AI cho Sinh viên*

---

## 🎯 Mục Tiêu Dự Án
Xây dựng pipeline dữ liệu hoàn chỉnh từ đầu đến cuối (**End-to-End**):
1. **Thu thập (Ingestion)**: Tự động tải danh sách 10.400+ mã công ty và báo cáo tài chính thường niên (Form 10-K) từ cổng **SEC EDGAR**.
2. **Làm sạch (Transformation)**: Chuẩn hóa mã CIK 10 chữ số, lưu trữ tối ưu dưới định dạng **Parquet Snappy** (tiết kiệm >75% dung lượng).
3. **Bóc tách văn bản AI**: Tước bỏ rác thẻ HTML/XBRL, trích xuất chuẩn xác phần giá trị nhất: **Item 1A - Risk Factors** sang định dạng **Markdown**.
4. **Cắt đoạn ngữ nghĩa (RAG Chunking)**: Phân mảnh tài liệu thành các chunks tối ưu (500 từ) kèm metadata phong phú sẵn sàng nạp vào Vector Database.

---

## 📂 Cấu Trúc Dự Án Chuẩn Modular

```text
D:\Hệ Thống\
│
├── 📁 config/                      # Cấu hình tập trung (YAML & Settings)
│   └── base_config.yaml           # Đường dẫn, tham số chunking, LLM model
│
├── 📁 data/                        # Hồ dữ liệu theo kiến trúc Medallion (Data Lake)
│   ├── 01_raw/                    # [Bronze] Dữ liệu thô từ SEC (JSON, HTML gốc)
│   │   ├── companies/             # all_companies.json
│   │   └── sec_filings/           # HTML 10-K các mã lớn (AAPL, GOOGL, MSFT,...)
│   ├── 02_staging/                # [Silver] Dữ liệu sạch cho AI
│   │   ├── companies_clean.parquet# Đã làm sạch CIK, khử trùng lặp
│   │   └── sec_filings/           # Markdown bóc tách (Item 1A Risk Factors)
│   ├── 03_primary/                # [Gold] Dữ liệu chuẩn bị cho Vector DB
│   │   └── chunks/                # Chunks JSON & Parquet kèm metadata
│   └── 04_curated/                # [Curated] Vector Store (Qdrant / Chroma)
│
├── 📁 src/                         # Mã nguồn module hóa (Modular Architecture)
│   ├── __init__.py
│   ├── common/                    # Tiện ích chung
│   │   ├── config.py              # Path resolver & nạp config
│   │   └── logger.py              # Ghi log chuẩn định dạng
│   ├── ingestion/                 # Module thu thập dữ liệu (ETL)
│   │   ├── extract_companies.py   # [Bước 1] Kéo danh mục công ty từ SEC
│   │   └── ingest_10k_filings.py  # [Bước 3] Tải báo cáo 10-K từ SEC
│   ├── transformation/            # Module làm sạch dữ liệu
│   │   ├── clean_companies.py     # [Bước 2] Chuẩn hóa CIK sang Parquet
│   │   └── clean_10k_to_text.py   # [Bước 4] Tước rác HTML sang Markdown
│   └── rag/                       # Module RAG phục vụ AI
│       └── chunking.py            # [Bước 5] Semantic chunking cho Vector DB
│
├── 📁 notebooks/                   # Jupyter Notebook báo cáo / demo đồ án
│   └── 01_pipeline_demo.ipynb     # Minh họa trực quan cho giảng viên
│
├── 📁 docs/                        # Tài liệu thuyết minh đồ án
│   └── architecture.md            # Sơ đồ kiến trúc & giải thích chi tiết
│
├── 📁 infra/                       # Môi trường chạy phụ trợ (Docker Compose)
│   └── docker-compose.yml         # Postgres, Qdrant Vector DB, MinIO
│
├── 📁 tests/                       # Unit Test kiểm thử pipeline
│   └── test_pipeline.py           # Kiểm tra chất lượng dữ liệu & schema
│
├── 🚀 run.py                       # Master Runner điều phối toàn bộ từ thư mục gốc
├── 📄 requirements.txt             # Danh sách thư viện Python cần cài
├── 📄 pyproject.toml               # Cấu hình dự án Python
├── 📄 .env.example                 # Mẫu file biến môi trường
└── 📄 .gitignore                   # Bỏ qua cache và file dữ liệu nặng
```

---

## 🚀 Hướng Dẫn Sử Dụng Nhanh

### 1. Cài đặt môi trường
Mở Terminal tại thư mục `D:\Hệ Thống>` và chạy:
```bash
pip install -r requirements.txt
```

### 2. Chạy Pipeline điều phối
Chạy file điều phối chính `run.py`:
```bash
# Xem menu lựa chọn bước:
python run.py

# Hoặc chạy trực tiếp từng bước:
python run.py 1    # [Bước 1] Kéo danh mục 10.400+ công ty từ SEC
python run.py 2    # [Bước 2] Chuẩn hóa CIK sang Parquet (Silver)
python run.py 3    # [Bước 3] Tải báo cáo tài chính 10-K (Bronze)
python run.py 4    # [Bước 4] Bóc tách HTML sang Markdown cho AI (Silver)
python run.py 5    # [Bước 5] Cắt đoạn Chunking cho RAG (Gold)

# Hoặc chạy toàn bộ luồng tự động:
python run.py all
```

### 3. Kiểm thử tự động (Unit Test)
```bash
pytest tests/ -v
```

---

## 📊 Kết Quả Đạt Được
- **Tiết kiệm dung lượng**: Dữ liệu danh mục công ty giảm hơn **76%** dung lượng khi chuyển từ JSON sang Parquet Snappy.
- **Làm sạch văn bản AI**: Bóc tách thành công văn bản HTML nặng ~2.6 MB thành Markdown sạch (~85 KB) chỉ chứa phần **Item 1A - Risk Factors**.
- **Sẵn sàng cho Vector DB**: Chia nhỏ thành các chunks ~500 từ có overlap 100 từ, kèm đầy đủ metadata (`chunk_id`, `ticker`, `year`, `section`).
