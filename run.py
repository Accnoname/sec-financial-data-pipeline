import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.ingestion.extract_companies import fetch_and_save_companies
from src.transformation.clean_companies import clean_companies
from src.ingestion.ingest_10k_filings import ingest_filings
from src.transformation.clean_10k_to_text import extract_all_risk_factors, extract_risk_factors
from src.rag.chunking import chunk_all_risk_factors, chunk_for_rag


def run_step_4(arg: str | None = None):
    if arg and arg.upper() not in ("ALL", "A"):
        return extract_risk_factors(arg)
    return extract_all_risk_factors()


def run_step_5(arg: str | None = None):
    if arg and arg.upper() not in ("ALL", "A"):
        return chunk_for_rag(arg)
    return chunk_all_risk_factors()


STEPS = {
    "1": ("Kéo danh mục 10.400+ công ty từ SEC EDGAR", fetch_and_save_companies),
    "2": ("Chuẩn hóa CIK & xuất Parquet Silver", clean_companies),
    "3": ("Tải báo cáo 10-K gốc của các tập đoàn lớn", ingest_filings),
    "4": ("Bóc tách Item 1A. Risk Factors sang Markdown Silver", run_step_4),
    "5": ("Semantic Chunking nạp Tầng Gold Parquet & JSON", run_step_5),
}


def print_banner():
    print("""
=============================================================================
 📈 SEC FINANCIAL DATA PIPELINE & AI RAG SYSTEM
 Medallion Architecture: Bronze -> Silver -> Gold
=============================================================================
 Hướng dẫn sử dụng:
   python run.py             : Hiển thị menu & chạy tự động toàn bộ (all)
   python run.py all         : Chạy toàn bộ pipeline (Bước 1 -> 5)
   python run.py 1           : [Bước 1] Kéo danh mục công ty từ SEC
   python run.py 2           : [Bước 2] Chuẩn hóa Parquet (Silver)
   python run.py 3           : [Bước 3] Tải Form 10-K gốc (Bronze)
   python run.py 4           : [Bước 4] Bóc tách Markdown Item 1A (tất cả các mã)
   python run.py 4 AAPL      : [Bước 4] Bóc tách riêng cho mã AAPL
   python run.py 5           : [Bước 5] Cắt đoạn Chunking (tất cả các mã)
   python run.py 5 GOOGL     : [Bước 5] Cắt đoạn Chunking riêng cho mã GOOGL
=============================================================================
""")


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("-h", "--help", "help"):
        print_banner()
        return

    print_banner()
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    sub_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if target in ("all", "a"):
        for step_id, (name, fn) in STEPS.items():
            print(f"\n===> [BƯỚC {step_id}] {name}...")
            fn()
    elif target in STEPS:
        name, fn = STEPS[target]
        print(f"\n===> [BƯỚC {target}] {name}...")
        if target in ("4", "5") and sub_arg:
            fn(sub_arg)
        else:
            fn()
    else:
        print(f"Tham số không hợp lệ: '{target}'. Vui lòng chọn từ 1 đến 5 hoặc 'all'.")
        sys.exit(1)

    print("\n[OK] Pipeline đã hoàn thành xuất sắc nhiệm vụ.")


if __name__ == "__main__":
    main()
