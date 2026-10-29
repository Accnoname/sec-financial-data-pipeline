"""
dags/sec_financial_pipeline_dag.py
==============================================================================
SEC Financial Data Pipeline & AI RAG System - Apache Airflow Master DAG
==============================================================================
Kiến trúc Medallion Lakehouse điều phối tự động:
  - Tầng Bronze : Kéo 10,400+ công ty từ SEC & Ingest báo cáo 10-K gốc.
  - Tầng Silver : Chuẩn hóa CIK sang Parquet & Bóc tách Item 1A Risk Factors.
  - Tầng Gold   : Semantic Chunking (Token-bounded sliding window).
  - Tầng Curated: Vector Embedding Indexing (ChromaDB Vector Store).
  - Delta Sensor: ShortCircuitOperator tự động bỏ qua downstream khi dữ liệu đã mới nhất.
==============================================================================
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator

# Đảm bảo Airflow nhận diện thư mục root của dự án trong sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.config import SILVER_DIR, GOLD_DIR, CURATED_DIR
from src.common.logger import get_logger

# Import trực tiếp các nghiệp vụ cốt lõi từ các tầng Medallion
from src.bronze.extract_companies import fetch_and_save_companies
from src.silver.clean_companies import clean_companies
from src.bronze.ingest_10k_filings import ingest_filings
from src.silver.clean_10k_to_text import extract_all_risk_factors
from src.gold.chunking import chunk_all_risk_factors
from src.curated.embedder import build_vector_index

logger = get_logger("airflow_sec_pipeline")


def task_ingest_with_sensor_check(**context) -> bool:
    """
    Sensor & Ingestion Step:
      1. Tải về báo cáo 10-K mới từ SEC nếu phát hiện thay đổi accession number.
      2. Nếu KHÔNG có báo cáo mới (has_changes=False) và các file tầng Silver/Gold/Curated
         đều đã có sẵn trên đĩa -> Trả về False để ShortCircuitOperator bỏ qua các task sau.
      3. Nếu CÓ báo cáo mới hoặc bất kỳ tầng nào thiếu file -> Trả về True để chạy tiếp.
    """
    dag_run = context.get("dag_run")
    force = False
    if dag_run and dag_run.conf:
        force = bool(dag_run.conf.get("force", False))

    summary = ingest_filings(force=force)
    has_changes = summary.get("has_changes", True) if isinstance(summary, dict) else True

    # Kiểm tra sự tồn tại của dữ liệu downstream
    silver_exists = (SILVER_DIR / "sec_filings").exists()
    gold_exists = (GOLD_DIR / "chunks" / "all_chunks.parquet").exists()
    curated_exists = (CURATED_DIR / "vector_db").exists()

    all_downstream_ready = silver_exists and gold_exists and curated_exists

    if not force and not has_changes and all_downstream_ready:
        logger.info(
            "Short-circuit kích hoạt: Không phát hiện báo cáo 10-K mới từ SEC "
            "và dữ liệu Gold/Curated đã sẵn sàng. Bỏ qua các bước downstream!"
        )
        return False

    logger.info("Phát hiện dữ liệu mới hoặc thiếu cache -> Tiếp tục chạy downstream pipeline.")
    return True


default_args = {
    "owner": "data_engineering",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="sec_financial_lakehouse_pipeline",
    default_args=default_args,
    description="Enterprise SEC 10-K Medallion Data Pipeline and AI RAG System",
    schedule_interval="0 2 * * *",  # Tự động chạy lúc 02:00 AM mỗi ngày
    catchup=False,
    max_active_runs=1,
    tags=["finance", "sec-edgar", "medallion", "rag", "production"],
) as dag:

    # --------------------------------------------------------------------------
    # BƯỚC 1: Kéo danh mục công ty từ SEC EDGAR (Tầng Bronze)
    # --------------------------------------------------------------------------
    step_1_fetch_companies = PythonOperator(
        task_id="step_1_fetch_sec_companies",
        python_callable=fetch_and_save_companies,
        doc_md="Kéo file company_tickers_exchange.json chứa hơn 10,400+ doanh nghiệp từ SEC.gov",
    )

    # --------------------------------------------------------------------------
    # BƯỚC 2: Chuẩn hóa CIK 10 chữ số và xuất Parquet Snappy (Tầng Silver)
    # --------------------------------------------------------------------------
    step_2_clean_companies = PythonOperator(
        task_id="step_2_clean_companies_silver",
        python_callable=clean_companies,
        doc_md="Chuẩn hóa CIK, khử trùng lặp và lưu thành companies_clean.parquet nén Snappy",
    )

    # --------------------------------------------------------------------------
    # BƯỚC 3: Delta Sensor & Tải Form 10-K (Tầng Bronze)
    # --------------------------------------------------------------------------
    step_3_sensor_ingest_10k = ShortCircuitOperator(
        task_id="step_3_sensor_and_ingest_10k",
        python_callable=task_ingest_with_sensor_check,
        doc_md="Quét SEC Submissions API. Nếu không có file mới -> Short-circuit skip downstream.",
    )

    # --------------------------------------------------------------------------
    # BƯỚC 4: Bóc tách Item 1A Risk Factors ra Markdown sạch (Tầng Silver)
    # --------------------------------------------------------------------------
    step_4_extract_risk_factors = PythonOperator(
        task_id="step_4_extract_item1a_markdown",
        python_callable=extract_all_risk_factors,
        doc_md="Dùng BeautifulSoup và RegEx bóc tách phần Item 1A Risk Factors loại bỏ thẻ rác HTML",
    )

    # --------------------------------------------------------------------------
    # BƯỚC 5: Semantic Chunking nạp Tầng Gold Parquet (Tầng Gold)
    # --------------------------------------------------------------------------
    step_5_chunk_risk_factors = PythonOperator(
        task_id="step_5_semantic_chunking_gold",
        python_callable=chunk_all_risk_factors,
        doc_md="Cắt đoạn văn bản ngữ nghĩa kèm sliding overlap và gán metadata phong phú",
    )

    # --------------------------------------------------------------------------
    # BƯỚC 6: Tạo Vector Embedding nạp ChromaDB (Tầng Curated)
    # --------------------------------------------------------------------------
    step_6_build_vector_store = PythonOperator(
        task_id="step_6_build_chroma_vector_store",
        python_callable=build_vector_index,
        doc_md="Tạo dense vector bằng SentenceTransformers và lập chỉ mục trong ChromaDB",
    )

    # --------------------------------------------------------------------------
    # Thiết lập thứ tự phụ thuộc (Topological Dependency Flow)
    # --------------------------------------------------------------------------
    step_1_fetch_companies >> step_2_clean_companies >> step_3_sensor_ingest_10k
    step_3_sensor_ingest_10k >> step_4_extract_risk_factors >> step_5_chunk_risk_factors >> step_6_build_vector_store
