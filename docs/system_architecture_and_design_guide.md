# Đặc Tả Kiến Trúc Hệ Thống và Hướng Dẫn Thiết Kế Kiến Trúc

**Phiên bản:** 2.1.0
**Hệ thống:** SEC Financial Data Pipeline và RAG System
**Repository:** Accnoname/sec-financial-data-pipeline

---

## Mục Lục

1. Tổng Quan Hệ Thống
2. Kiến Trúc Kho Dữ Liệu Medallion Lakehouse
3. Phân Rã Các Module Chức Năng (`src/`)
4. Tầng Điều Phối và Tiêu Thụ
5. Hướng Dẫn Luồng End-to-End: Từ Thu Thập Đến Trình Bày
6. Phương Pháp Luận Thiết Kế Kiến Trúc
   - 6.1 Tư Duy Thiết Kế Từ Ngoài Vào (Outside-In)
   - 6.2 Nguyên Lý Bất Biến và Tính Khả Hoàn
   - 6.3 Hợp Đồng Dữ Liệu (Data Contracts)
   - 6.4 Ma Trận Đánh Đổi Kỹ Thuật (Trade-Off Matrix)
   - 6.5 Xử Lý Bất Thường Trong Dữ Liệu Thực Tế
   - 6.6 Lộ Trình Tiến Hóa V1 lên V2
7. Kiến Trúc Kiểm Thử và Đảm Bảo Chất Lượng

---

## 1. Tổng Quan Hệ Thống

SEC Financial Data Pipeline và RAG System là hệ thống kỹ thuật dữ liệu tự động hóa toàn diện, kết hợp với cơ chế hỏi đáp AI dựa trên kỹ thuật Retrieval-Augmented Generation (RAG). Hệ thống thu thập báo cáo tài chính thường niên Form 10-K từ cổng thông tin SEC EDGAR của Ủy ban Chứng khoán Hoa Kỳ, làm sạch tài liệu HTML/XBRL phi cấu trúc có dung lượng lớn, tách biệt phần công bố rủi ro kinh doanh chiến lược (Item 1A. Risk Factors), và tổ chức dữ liệu thành các đoạn ngữ nghĩa (semantic chunks) được lưu dưới dạng cột Parquet tối ưu cho việc đánh chỉ mục vector.

**Dữ liệu đầu vào:** Báo cáo Form 10-K của 7 tập đoàn công nghệ Mỹ: AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA.

**Sản phẩm đầu ra:** 262 đoạn ngữ nghĩa (semantic chunks) kèm metadata đầy đủ, sẵn sàng nạp vào Vector Database phục vụ hỏi đáp AI.

---

## 2. Kiến Trúc Kho Dữ Liệu Medallion Lakehouse

Dữ liệu được tổ chức qua 4 tầng chất lượng tăng dần, mỗi tầng có chuẩn định dạng, nén và hợp đồng schema riêng biệt.

```text
+------------------------------------------------------------------------------------+
|                          CẤU TRÚC LƯU TRỮ VẬT LÝ                                 |
+------------------------------------------------------------------------------------+

data/
|-- 01_raw/                          [BRONZE: Dữ liệu gốc bất biến từ nguồn]
|   |-- companies/
|   |   `-- all_companies.json       (~10.400 công ty từ SEC EDGAR)
|   `-- sec_filings/
|       |-- AAPL/aapl-20250927.htm   (File HTML/XBRL 10-K gốc, 2 đến 8 MB)
|       |-- AMZN/amzn-20251231.htm
|       |-- GOOGL/goog-20251231.htm
|       |-- META/meta-20251231.htm
|       |-- MSFT/msft-20260630.htm
|       |-- NVDA/nvda-20260125.htm
|       `-- TSLA/tsla-20251231.htm
|
|-- 02_staging/                      [SILVER: Đã làm sạch và cấu trúc hóa]
|   |-- companies_clean.parquet      (CIK chuẩn hóa 10 chữ số, loại trùng, Snappy)
|   `-- sec_filings/
|       |-- AAPL/AAPL_2025_risk_factors.md
|       |-- AMZN/AMZN_2025_risk_factors.md
|       |-- GOOGL/GOOGL_2025_risk_factors.md
|       |-- META/META_2025_risk_factors.md
|       |-- MSFT/MSFT_2026_risk_factors.md
|       |-- NVDA/NVDA_2026_risk_factors.md
|       `-- TSLA/TSLA_2025_risk_factors.md
|
|-- 03_primary/                      [GOLD: Đoạn ngữ nghĩa đã làm giàu metadata]
|   `-- chunks/
|       |-- AAPL_2025_chunks.parquet va .json
|       |-- AMZN_2025_chunks.parquet va .json
|       |-- GOOGL_2025_chunks.parquet va .json
|       |-- META_2025_chunks.parquet va .json
|       |-- MSFT_2026_chunks.parquet va .json
|       |-- NVDA_2026_chunks.parquet va .json
|       |-- TSLA_2025_chunks.parquet va .json
|       `-- all_chunks.parquet       (Tổng hợp 262 chunks toàn bộ 7 công ty)
|
`-- 04_curated/                      [CURATED: Chỉ mục Vector phục vụ RAG]
    `-- vector_db/                   (Chroma / Qdrant / FAISS)
```

### Đặc Tả Kỹ Thuật Từng Tầng

| Tầng | Đường dẫn | Định dạng | Nén | Hợp đồng nội dung |
|---|---|---|---|---|
| **Bronze** | `data/01_raw/` | JSON, HTML/XBRL | Không nén | Bản sao nguyên vẹn từng byte từ SEC API. Chỉ đọc sau khi ghi (Immutable). |
| **Silver - Companies** | `data/02_staging/` | Apache Parquet | Snappy | Cột `cik_str` (string, 10 ký tự có đệm số 0), `ticker`, `title`. Không trùng lặp. |
| **Silver - Filings** | `data/02_staging/` | Markdown | UTF-8 | Văn bản Item 1A thuần túy. Không chứa thẻ script, style hay mã XBRL. Độ dài tối thiểu 10.000 ký tự. |
| **Gold** | `data/03_primary/` | Apache Parquet / JSON | Snappy | Cột: `chunk_id`, `ticker`, `fiscal_year`, `section`, `chunk_index`, `word_count`, `text`. |
| **Curated** | `data/04_curated/` | Vector Index | Nhị phân | Vector dày đặc (384 đến 1.536 chiều) ánh xạ với `chunk_id` và metadata tại tầng Gold. |

---

## 3. Phân Rã Các Module Chức Năng (`src/`)

```text
src/
|-- common/
|   |-- config.py             # Định vị đường dẫn gốc dự án và hằng số thư mục
|   `-- logger.py             # Ghi log chuẩn ISO timestamp đồng nhất toàn hệ thống
|-- ingestion/
|   |-- extract_companies.py  # Thu thập danh mục công ty từ SEC EDGAR API
|   `-- ingest_10k_filings.py # Tải báo cáo Form 10-K với kiểm soát tốc độ (rate limit)
|-- transformation/
|   |-- clean_companies.py    # Chuẩn hóa CIK, loại trùng lặp, xuất Parquet
|   `-- clean_10k_to_text.py  # Phân tích DOM, lọc thẻ rác, trích xuất Item 1A bằng RegEx
`-- rag/
    |-- chunking.py           # Cắt đoạn cửa sổ trượt và tạo metadata đi kèm
    |-- embedder.py           # Tạo vector embedding bằng sentence-transformers, nạp ChromaDB
    `-- retriever.py          # Truy vấn ngữ nghĩa và tổng hợp câu trả lời qua Gemini API
```

### Chi Tiết Từng Module

**`src/common/config.py`**
- Xác định `PROJECT_ROOT` bằng cách duyệt ngược từ vị trí file, không phụ thuộc thư mục làm việc khi chạy lệnh.
- Khởi tạo tự động các thư mục data nếu chưa tồn tại (`mkdir(parents=True, exist_ok=True)`).

**`src/ingestion/extract_companies.py`**
- Gọi `https://www.sec.gov/files/company_tickers_exchange.json`.
- Khai báo HTTP header `User-Agent` đúng định dạng SEC quy định.
- Ghi kết quả xuống `data/01_raw/companies/all_companies.json`.

**`src/ingestion/ingest_10k_filings.py`**
- Tra cứu `https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json` để tìm số hồ sơ (accession number) của bản 10-K mới nhất.
- Tải file `.htm` về `data/01_raw/sec_filings/{TICKER}/`.
- Đảm bảo khoảng cách giữa các request để không vượt giới hạn 10 req/giây của SEC.

**`src/transformation/clean_companies.py`**
- Chuyển đổi CIK số nguyên sang chuỗi 10 ký tự có đệm số 0 (`str(cik).zfill(10)`).
- Loại bỏ ticker trùng lặp (`drop_duplicates(subset=['ticker'])`).
- Lưu ra `data/02_staging/companies_clean.parquet` dùng engine PyArrow với nén Snappy.

**`src/transformation/clean_10k_to_text.py`**
- Phân tích cây DOM bằng BeautifulSoup với parser `lxml`.
- Xóa toàn bộ thẻ `<script>`, `<style>`, `<ix:header>`.
- Chuẩn hóa khoảng trắng để xử lý hiện tượng ngắt dòng tùy ý trong file HTML tài chính.
- Áp dụng RegEx giới hạn biên để tách đoạn từ `ITEM 1A. RISK FACTORS` đến tiêu mục tiếp theo.
- Xuất văn bản Markdown sạch ra tầng Silver.

**`src/rag/chunking.py`**
- Đọc file Markdown từ tầng Silver.
- Cắt đoạn theo cửa sổ trượt 500 từ, gối đầu 100 từ.
- Gắn metadata: `chunk_id` định dạng `{TICKER}_{YEAR}_{INDEX:04d}`, mã cổ phiếu, năm tài chính, tên mục, số từ.
- Lưu file Parquet cho từng công ty và tổng hợp vào `all_chunks.parquet`.

---

## 4. Tầng Điều Phối và Tiêu Thụ

```text
[Giao diện dòng lệnh: run.py]
  python run.py 1           # Bước 1: Thu thập danh mục công ty
  python run.py 2           # Bước 2: Chuẩn hóa sang Parquet Silver
  python run.py 3           # Bước 3: Tải báo cáo Form 10-K
  python run.py 4           # Bước 4: Trích xuất Item 1A sang Markdown
  python run.py 4 AAPL      # Bước 4 chỉ cho mã AAPL
  python run.py 5           # Bước 5: Cắt đoạn Chunking sang Gold
  python run.py 5 GOOGL     # Bước 5 chỉ cho mã GOOGL
  python run.py all         # Chạy toàn bộ từ Bước 1 đến 5

[Giao diện truy vấn dữ liệu trực tiếp - Dành cho phân tích viên]
  - Truy vấn SQL tốc độ cao trực tiếp trên file Parquet qua DuckDB hoặc Polars:
    SELECT ticker, fiscal_year, word_count, text
    FROM read_parquet('data/03_primary/chunks/all_chunks.parquet')
    WHERE ticker = 'NVDA' AND text LIKE '%artificial intelligence%';

[Hệ thống AI RAG - Tầng Curated]
  - Mô hình embedding: Sentence-Transformers (ví dụ: all-MiniLM-L6-v2)
  - Vector Store: Qdrant / Chroma / FAISS (chạy local qua docker-compose.yml)
  - Truy xuất: Tìm kiếm độ tương đồng Cosine, top-k kết quả
  - Tổng hợp LLM: So sánh rủi ro giữa nhiều tập đoàn theo câu hỏi ngôn ngữ tự nhiên

[Hạ tầng dịch vụ - docker-compose.yml]
  - postgres: Data Warehouse cục bộ (cổng 5432)
  - qdrant: Vector Database (cổng 6333/6334)
  - minio: Object Storage tương thích S3 / Data Lake cục bộ (cổng 9000/9001)
```

---

## 5. Hướng Dẫn Luồng End-to-End: Từ Thu Thập Đến Trình Bày

Đây là bản đồ toàn bộ hành trình của dữ liệu từ nguồn thô đến giao diện phục vụ người dùng cuối.

```text
=================================================================================
   LUONG END-TO-END: SEC EDGAR -> DATA LAKE -> RAG AI
=================================================================================

BUOC 1: THU THAP DANH MUC CONG TY
    Lenh: python run.py 1
    Module: src/ingestion/extract_companies.py
    |
    |  GET https://www.sec.gov/files/company_tickers_exchange.json
    |  Header: User-Agent: <Ten> <Email>
    |
    v  data/01_raw/companies/all_companies.json (~10.400 cong ty)

---------------------------------------------------------------------------------

BUOC 2: CHUAN HOA DANH MUC CONG TY
    Lenh: python run.py 2
    Module: src/transformation/clean_companies.py
    |
    |  Doc: data/01_raw/companies/all_companies.json
    |  - CIK: so nguyen 320193 -> chuoi "0000320193" (zfill(10))
    |  - Loai ticker trung lap (drop_duplicates)
    |  - Nen bang Snappy Parquet: giam ~76% dung luong
    |
    v  data/02_staging/companies_clean.parquet

---------------------------------------------------------------------------------

BUOC 3: TAI BAO CAO FORM 10-K
    Lenh: python run.py 3
    Module: src/ingestion/ingest_10k_filings.py
    |
    |  Voi moi ticker trong danh sach (AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA):
    |  1. Tra cuu submissions API: GET https://data.sec.gov/submissions/CIK0000320193.json
    |  2. Tim accession number cua ban 10-K moi nhat
    |  3. Tai file .htm chinh: GET https://www.sec.gov/Archives/edgar/data/.../file.htm
    |  4. Nghi 0.1 giay giua moi request (tuan thu <= 10 req/giay)
    |
    v  data/01_raw/sec_filings/{TICKER}/*.htm (2 - 8 MB moi file)

---------------------------------------------------------------------------------

BUOC 4: TRICH XUAT ITEM 1A. RISK FACTORS
    Lenh: python run.py 4
    Module: src/transformation/clean_10k_to_text.py
    |
    |  Voi moi file .htm:
    |  1. Phan tich cay DOM bang BeautifulSoup (lxml)
    |  2. Xoa toan bo the <script>, <style>, <ix:header>
    |  3. Lay toan bo noi dung van ban thuan (.get_text)
    |  4. Chuan hoa khoang trang (xu ly ngat dong tuy y trong HTML)
    |  5. Tim tieu muc bat dau bang RegEx linh hoat:
    |     pattern = r"ITEM\s+1A[\.\:\s\-]+RISK\s+FACTORS" (re.IGNORECASE)
    |  6. Tim ranh gioi ket thuc (ITEM 1B hoac ITEM 2)
    |  7. Ghi van ban Markdown sach
    |
    v  data/02_staging/sec_filings/{TICKER}/{TICKER}_{YEAR}_risk_factors.md
       (> 10.000 ky tu / file, van ban van xuoi thuan khiet)

---------------------------------------------------------------------------------

BUOC 5: CAT DOAN NGAN NGHIA (SEMANTIC CHUNKING)
    Lenh: python run.py 5
    Module: src/rag/chunking.py
    |
    |  Voi moi file Markdown:
    |  1. Tach van ban thanh danh sach tu (word tokenization)
    |  2. Ap dung cua so truot:
    |     - Kich thuoc cua so: 500 tu
    |     - Buoc truot: 400 tu (goi dau 100 tu)
    |  3. Tao metadata cho tung chunk:
    |     chunk_id   = "{TICKER}_{YEAR}_{INDEX:04d}"
    |     ticker     = "AAPL"
    |     fiscal_year = 2025
    |     section    = "Item 1A. Risk Factors"
    |     word_count = <so tu thuc te>
    |     text       = <noi dung doan van>
    |  4. Ghi file Parquet rieng tung cong ty + tong hop
    |
    v  data/03_primary/chunks/all_chunks.parquet (262 chunks, 7 cong ty)

---------------------------------------------------------------------------------

BUOC 6: TAO EMBEDDING VA NAP VAO VECTOR DATABASE
    (Buoc tiep theo - Tang Curated, chua trien khai)
    Module: src/rag/embedder.py (se xay dung)
    |
    |  Buoc 6a - Tao Vector Embedding:
    |  1. Doc 262 chunks tu all_chunks.parquet
    |  2. Gui tung doan text qua mo hinh embedding:
    |     - Local: all-MiniLM-L6-v2 (Sentence-Transformers, mien phi)
    |     - Cloud: text-embedding-3-small (OpenAI)
    |  3. Moi chunk tao ra 1 vector so thuc (vi du: 384 chieu)
    |
    |  Buoc 6b - Nap vao Vector Store (Qdrant chay qua docker-compose):
    |  1. Ket noi Qdrant tai localhost:6333
    |  2. Tao collection "sec_risk_factors"
    |  3. Nap tung cap (vector, metadata) vao collection
    |
    v  data/04_curated/vector_db/ (chi muc vector da danh)

---------------------------------------------------------------------------------

BUOC 7: HE THONG HOI DAP RAG
    (Buoc tiep theo - Giao dien nguoi dung, chua trien khai)
    Module: src/rag/retriever.py (se xay dung)
    |
    |  Nguoi dung dat cau hoi bang ngon ngu tu nhien:
    |  "Rui ro ve chuoi cung ung chip cua Nvidia nam 2026 la gi?"
    |
    |  1. Chuyen cau hoi thanh vector embedding (cung mo hinh voi buoc 6)
    |  2. Tim kiem Cosine Similarity trong Qdrant -> lay top-5 chunks lien quan
    |  3. Ghep noi chunks lam context cho LLM:
    |     prompt = "Dua vao cac doan van sau: {context}\n\nTra loi: {cau_hoi}"
    |  4. Goi LLM (Gemini / GPT-4) de tong hop cau tra loi
    |
    v  Cau tra loi tong hop kem trich dan nguon goc (ticker, nam, muc)

=================================================================================
```

---

## 6. Phương Pháp Luận Thiết Kế Kiến Trúc

### 6.1 Tư Duy Thiết Kế Từ Ngoài Vào (Outside-In)

Sai lầm phổ biến của người mới bắt đầu là tư duy **Inside-Out**: tải dữ liệu về trước, viết code thử nghiệm, rồi cuối cùng mới nhận ra dữ liệu không đúng định dạng yêu cầu của ứng dụng.

Cách tiếp cận đúng là **Outside-In** (từ đích đến ngược về nguồn gốc):
1. **Người dùng cuối cần gì?** Câu trả lời từ AI về rủi ro cụ thể, có trích dẫn nguồn gốc rõ ràng.
2. **LLM cần gì?** Đoạn văn súc tích (400-500 từ), có nhãn công ty và năm tài chính.
3. **Tầng Gold cần gì?** Bảng phẳng Parquet gồm `text`, `ticker`, `fiscal_year`, `chunk_id`.
4. **Tầng Silver cần gì?** Văn bản Markdown thuần túy không có thẻ HTML, để đếm từ chính xác.
5. **Tầng Bronze cần gì?** Bản gốc nguyên vẹn từ SEC để có thể chạy lại khi thuật toán thay đổi.

### 6.2 Nguyên Lý Bất Biến và Tính Khả Hoàn

Mọi hàm xử lý dữ liệu phải thỏa mãn:
```text
f(f(x)) = f(x)
```
Chạy `python run.py 4 AAPL` một lần hay mười lần phải cho ra kết quả giống hệt nhau. Tầng Bronze là bất biến (chỉ đọc sau khi ghi).

### 6.3 Hợp Đồng Dữ Liệu (Data Contracts)

Hợp đồng dữ liệu là cam kết tường minh về schema, kiểu dữ liệu và nội dung giữa module tạo ra và module tiêu thụ dữ liệu.

| Hợp đồng | Quy tắc | Hậu quả nếu vi phạm |
|---|---|---|
| CIK 10 chữ số | `cik_str` phải là chuỗi 10 ký tự có đệm số 0 | Truy vấn API SEC thất bại hoàn toàn |
| Độ dài Item 1A | Tối thiểu 10.000 ký tự | Vector embedding bị rác hóa mà không có lỗi cú pháp |
| Schema Gold chunk | `chunk_id` duy nhất, `word_count > 0`, `text` không rỗng | Hỏng chỉ mục Vector Store |

### 6.4 Ma Trận Đánh Đổi Kỹ Thuật (Trade-Off Matrix)

| Quyết định | Giải pháp đã chọn | Lý do kỹ thuật cụ thể |
|---|---|---|
| Định dạng lưu bảng | Apache Parquet (Snappy) | Giảm từ 921 KB JSON xuống 359 KB Parquet (giảm 61%). Đọc theo cột: chỉ tải cột cần thiết, bỏ qua phần còn lại. |
| Trích xuất văn bản | BeautifulSoup + RegEx | File 10-K nặng 2-8 MB. Dùng LLM tốn tiền (0.5 - 2 USD/file) và chậm. Parser DOM cục bộ chạy < 300ms, chi phí bằng 0. |
| Chiến lược cắt đoạn | Cửa sổ từ 500 / gối 100 | Cắt theo ký tự chém ngang thuật ngữ tài chính. Cắt theo từ bảo toàn ranh giới ngữ nghĩa. 100 từ gối đầu giữ nguyên mạch lập luận ở biên chunk. |
| Điều phối pipeline | Python CLI (`run.py`) | Hệ thống dưới 100 công ty không cần Airflow. Mỗi hàm trong `src/` có thể gói vào `PythonOperator` Airflow trong 5 phút khi cần mở rộng. |

### 6.5 Xử Lý Bất Thường Trong Dữ Liệu Thực Tế

```text
Hiện tượng: Thẻ HTML bị ngắt giữa tiêu đề tại Microsoft (MSFT)
-----------------------------------------------------------------
File HTML của MSFT chứa:  <span>RIS</span>\n<span>K FACTORS</span>

Hậu quả:
  RegEx thông thường r"ITEM 1A\. RISK FACTORS" thất bại hoàn toàn.
  Kết quả trả về là chuỗi rỗng. Pipeline không báo lỗi.

Giải pháp:
  1. Lấy toàn bộ text từ DOM trước (BeautifulSoup .get_text())
  2. Dùng RegEx linh hoạt cho phép khoảng trắng tùy ý:
     r"ITEM\s+1A[\.\:\s\-]+RISK\s+FACTORS"
  3. Bật re.IGNORECASE | re.MULTILINE

Bài học tổng quát:
  Khi xử lý HTML tài chính thực tế, không bao giờ giả định văn bản
  trong thẻ là liền mạch. Luôn trích xuất text trước, sau đó
  mới áp dụng pattern matching.
```

### 6.6 Lộ Trình Tiến Hóa V1 lên V2

| Chiều cạnh | V1 hiện tại (Single-Node) | V2 mục tiêu (Phân tán, Đám mây) |
|---|---|---|
| Lưu trữ | Ổ đĩa cục bộ (`data/`) | AWS S3 / Google Cloud Storage |
| Catalog bảng | File Parquet riêng lẻ | Apache Iceberg / Delta Lake |
| Tính toán | Python / Pandas đơn tiến trình | DuckDB / Apache Spark |
| Điều phối | Python CLI | Apache Airflow (Cloud Composer) |
| Vector Store | FAISS in-memory / Chroma nhúng | Qdrant Cluster / Milvus |
| Tần suất chạy | Thủ công theo yêu cầu | Tự động theo sự kiện (SEC RSS Feed) |

---

## 7. Kiến Trúc Kiểm Thử và Đảm Bảo Chất Lượng

Kiểm thử là một tầng kiến trúc độc lập bảo vệ hệ thống trước mọi thay đổi mã nguồn.

```text
tests/
|-- test_pipeline.py         # Kiểm tra tích hợp toàn bộ tầng Medallion
|   |-- test_raw_companies_json_exists       # Bronze: all_companies.json tồn tại
|   |-- test_raw_sec_filings_exist           # Bronze: 7 file .htm đã được tải
|   |-- test_staging_parquet_schema          # Silver: CIK đúng chuẩn 10 chữ số
|   |-- test_markdown_risk_factors_all_tickers  # Silver: Markdown > 10.000 ký tự
|   `-- test_gold_chunks_schema_and_content  # Gold: Schema và nội dung chunk hợp lệ
|
`-- unit/
    `-- test_units.py        # Kiểm tra logic đơn lẻ, không phụ thuộc ổ đĩa hay mạng
        |-- test_config_directories          # Định vị đường dẫn thư mục
        |-- test_split_into_chunks_basic     # Toán học cửa sổ trượt và gối đầu
        |-- test_split_into_chunks_empty     # Xử lý đầu vào rỗng
        |-- test_cik_normalization_logic     # Đệm số 0 vào CIK
        |-- test_item_1a_regex_matching      # Độ bền vững của RegEx tên tiêu đề
        `-- test_run_steps_registration      # Tất cả bước CLI đã đăng ký đủ
```

**Lệnh chạy kiểm thử:**
```powershell
python -m pytest -v
```
