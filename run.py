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


def run_step_6():
    """Bước 6: Tạo vector embedding và nạp vào ChromaDB (Tầng Curated)."""
    from src.rag.embedder import build_vector_index
    return build_vector_index()


def run_step_7(question: str | None = None):
    """Bước 7: Hỏi đáp RAG bằng Gemini API."""
    from src.rag.retriever import rag_query
    if not question:
        print("Dùng: python run.py 7 \"Cau hoi cua ban\"")
        print("Vi du: python run.py 7 \"What are Nvidia AI risks in 2026?\"")
        sys.exit(1)
    return rag_query(question)


STEPS = {
    "1": ("Kéo danh mục 10.400+ công ty từ SEC EDGAR", fetch_and_save_companies),
    "2": ("Chuẩn hóa CIK & xuất Parquet Silver", clean_companies),
    "3": ("Tải báo cáo 10-K gốc của các tập đoàn lớn", ingest_filings),
    "4": ("Bóc tách Item 1A. Risk Factors sang Markdown Silver", run_step_4),
    "5": ("Semantic Chunking nạp Tầng Gold Parquet & JSON", run_step_5),
    "6": ("Tạo vector embedding & nạp vào ChromaDB (Tầng Curated)", run_step_6),
    "7": ("RAG Query: Hỏi đáp tài chính bằng Gemini AI", run_step_7),
}


def print_banner():
    print("""
=============================================================================
 SEC FINANCIAL DATA PIPELINE & AI RAG SYSTEM
 Medallion Architecture: Bronze -> Silver -> Gold -> Curated
=============================================================================
 Huong dan su dung:
   python run.py             : Hien thi menu
   python run.py all         : Chay toan bo pipeline (Buoc 1 -> 5)
   python run.py 1           : [Buoc 1] Keo danh muc cong ty tu SEC
   python run.py 2           : [Buoc 2] Chuan hoa Parquet (Silver)
   python run.py 3           : [Buoc 3] Tai Form 10-K goc (Bronze)
   python run.py 4           : [Buoc 4] Boc tach Markdown Item 1A
   python run.py 4 AAPL      : [Buoc 4] Boc tach rieng cho ma AAPL
   python run.py 5           : [Buoc 5] Cat doan Chunking (Gold)
   python run.py 5 GOOGL     : [Buoc 5] Cat doan rieng cho ma GOOGL
   python run.py 6           : [Buoc 6] Tao Vector Index (ChromaDB)
   python run.py 7 "cau hoi" : [Buoc 7] Hoi dap RAG bang Gemini AI
=============================================================================
""")


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("-h", "--help", "help"):
        print_banner()
        return

    print_banner()
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "menu"
    sub_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if target == "menu":
        return

    if target in ("all", "a"):
        # "all" chay buoc 1 den 5 (pipeline data engineering)
        for step_id in ["1", "2", "3", "4", "5"]:
            name, fn = STEPS[step_id]
            print(f"\n===> [BUOC {step_id}] {name}...")
            fn()
    elif target in STEPS:
        name, fn = STEPS[target]
        print(f"\n===> [BUOC {target}] {name}...")
        if target in ("4", "5") and sub_arg:
            fn(sub_arg)
        elif target == "7":
            fn(sub_arg)
        else:
            fn()
    else:
        print(f"Tham so khong hop le: '{target}'. Chon tu 1 den 7 hoac 'all'.")
        sys.exit(1)

    print("\n[OK] Hoan thanh.")


if __name__ == "__main__":
    main()
