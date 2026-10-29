# Hướng Dẫn Vận Hành Apache Airflow cho SEC Financial Pipeline

Tài liệu này hướng dẫn chi tiết cách khởi động, vận hành và giám sát luồng dữ liệu tự động với **Apache Airflow 2.9** trên môi trường Docker.

---

## 1. Cấu Trúc Các Thành Phần Đã Thiết Lập

1. **[`Dockerfile.airflow`](file:///d:/sec-financial-data-pipeline/Dockerfile.airflow)**:
   - Dựa trên image chính thức `apache/airflow:2.9.2-python3.10`.
   - Cài đặt sẵn toàn bộ các thư viện của dự án (`pandas`, `pyarrow`, `beautifulsoup4`, `sentence-transformers`, `chromadb`,...).
   - Thiết lập `PYTHONPATH` nhận diện gói `src.*`.

2. **[`docker-compose.airflow.yml`](file:///d:/sec-financial-data-pipeline/docker-compose.airflow.yml)**:
   - `airflow-postgres`: Cơ sở dữ liệu metadata cho Airflow (Port 5433).
   - `airflow-init`: Tự động khởi tạo database và tạo tài khoản Admin.
   - `airflow-webserver`: Giao diện Web UI quản trị (Port 8080).
   - `airflow-scheduler`: Tiến trình điều phối, lập lịch và quét DAGs.

3. **[`dags/sec_financial_pipeline_dag.py`](file:///d:/sec-financial-data-pipeline/dags/sec_financial_pipeline_dag.py)**:
   - DAG chính điều phối toàn bộ 4 tầng Medallion:
     - `step_1_fetch_sec_companies` (Bronze)
     - `step_2_clean_companies_silver` (Silver)
     - `step_3_sensor_and_ingest_10k` (ShortCircuit Delta Sensor)
     - `step_4_extract_item1a_markdown` (Silver)
     - `step_5_semantic_chunking_gold` (Gold)
     - `step_6_build_chroma_vector_store` (Curated)

---

## 2. Hướng Dẫn Khởi Động Từng Bước

### Bước 1: Mở ứng dụng Docker Desktop
- Đảm bảo ứng dụng **Docker Desktop** trên máy tính Windows của bạn đang được bật (biểu tượng cá voi màu xanh lá cây ở thanh taskbar).

### Bước 2: Build image và khởi chạy các container
Mở Terminal tại thư mục gốc dự án và chạy lệnh:
```bash
docker compose -f docker-compose.airflow.yml up -d --build
```
> **Lưu ý ở lần chạy đầu tiên**: Docker sẽ tải image và build các dependencies (`requirements.txt`). Quá trình này mất khoảng 2-3 phút tùy thuộc tốc độ mạng.

### Bước 3: Kiểm tra trạng thái các container
```bash
docker compose -f docker-compose.airflow.yml ps
```
Khi thấy cả 3 container `airflow_postgres`, `airflow_webserver`, và `airflow_scheduler` đều ở trạng thái `running` (hoặc `healthy`), hệ thống đã sẵn sàng.

---

## 3. Truy Cập Giao Diện Web UI

1. Mở trình duyệt và truy cập: [http://localhost:8080](http://localhost:8080)
2. Đăng nhập bằng tài khoản mặc định:
   - **Username**: `admin`
   - **Password**: `admin`

3. Bạn sẽ thấy DAG: `sec_financial_lakehouse_pipeline`.
   - **Bật công tắc (Toggle ON)** ở cột trái để kích hoạt lập lịch tự động (02:00 AM hàng ngày).
   - **Bấm nút Play (Trigger DAG)** ở góc phải nếu muốn chạy thử nghiệm ngay lập tức.
   - Nếu muốn ép buộc tải lại toàn bộ từ đầu (Force Recompute), bấm **Trigger DAG w/ config** và nhập:
     ```json
     {"force": true}
     ```

---

## 4. Kiểm Tra & Giám Sát Luồng Chạy

- **Graph View**: Xem trực quan luồng dữ liệu theo hình cây.
  - Xanh lá cây nhạt: Đang chạy (`running`).
  - Xanh lá cây đậm: Thành công (`success`).
  - Màu hồng pastel: Bỏ qua (`skipped` - do ShortCircuit phát hiện dữ liệu SEC không có thay đổi).
- **Log từng Task**: Bấm trực tiếp vào bất kỳ ô task nào và chọn nút **Log** để xem tiến trình thực thi chi tiết.

---

## 5. Dừng Hệ Thống Khi Không Sử Dụng (Giải Phóng RAM)

Khi muốn tắt cụm Airflow để tiết kiệm tài nguyên máy tính:
```bash
docker compose -f docker-compose.airflow.yml down
```
*(Dữ liệu trong database Postgres và các file dữ liệu trong `data/` vẫn được bảo toàn nguyên vẹn trên đĩa)*.
