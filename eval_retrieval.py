import os
import sys
import json
import argparse
from typing import List, Dict, Any
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.config import PRIMARY_DIR
from src.rag.hybrid_retriever import HybridRetriever

# Lazy global retriever instance to avoid re-initializing encoder and ChromaDB per query
_RETRIEVER: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _RETRIEVER
    if _RETRIEVER is None:
        _RETRIEVER = HybridRetriever()
    return _RETRIEVER


# ==========================================
# 1. BỐN ADAPTER NỐI VÀO REPO
# ==========================================
def load_all_chunk_texts() -> List[Dict[str, Any]]:
    """
    Load toàn bộ chunks (gồm chunk_id, text, metadata) từ file Gold Parquet.
    """
    parquet_path = PRIMARY_DIR / "chunks" / "all_chunks.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"Chưa tìm thấy file {parquet_path}. Hãy chạy chunking trước.")
    df = pd.read_parquet(parquet_path)
    return df.to_dict(orient="records")


def dense_retrieve(query: str, ticker: str, year: int, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Truy vấn chỉ dùng Vector Store (ChromaDB) với metadata filtering.
    Trả về list dict, mỗi phần tử có: {"chunk_id": ..., "text": ...}
    """
    retriever = get_retriever()
    results = retriever._dense_search(
        query=query,
        candidate_count=top_k,
        ticker=ticker,
        year=year,
    )
    if not results and year:
        # Fallback without year filter if year mismatch exists
        results = retriever._dense_search(
            query=query,
            candidate_count=top_k,
            ticker=ticker,
        )
    return results


def bm25_retrieve(query: str, ticker: str, year: int, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Truy vấn chỉ dùng BM25 với metadata filtering.
    """
    retriever = get_retriever()
    results = retriever.bm25_index.search(
        query=query,
        top_k=top_k,
        ticker=ticker,
        year=year,
    )
    if not results and year:
        results = retriever.bm25_index.search(
            query=query,
            top_k=top_k,
            ticker=ticker,
        )
    return results


def hybrid_retrieve(query: str, ticker: str, year: int, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Truy vấn kết hợp Dense + BM25 qua RRF (k=60).
    """
    retriever = get_retriever()
    results = retriever.retrieve(
        query=query,
        top_k=top_k,
        candidate_pool_size=15,
        ticker=ticker,
        year=year,
    )
    if not results and year:
        results = retriever.retrieve(
            query=query,
            top_k=top_k,
            candidate_pool_size=15,
            ticker=ticker,
        )
    return results


# ==========================================
# 2. LOGIC KIỂM TRA ANCHOR & ĐÁNH GIÁ METRICS
# ==========================================
def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def check_anchors(questions: List[Dict[str, Any]], all_chunks: List[Dict[str, Any]]):
    """Xác nhận xem mỗi anchor text có xuất hiện trọn vẹn trong ít nhất 1 chunk không"""
    print("\n[KIEM TRA ANCHOR] Dang kiem tra tinh toan ven cua cac Anchor Texts...")
    missing = 0
    for q in questions:
        anchor_norm = normalize_text(q["anchor_text"])
        found = False
        for c in all_chunks:
            if c.get("ticker") == q["ticker"] and anchor_norm in normalize_text(c["text"]):
                found = True
                break
        if not found:
            print(f"CANH BAO: Anchor cau {q['id']} ({q['ticker']}) khong tim thay trong bat ky chunk nao:")
            print(f"   Anchor: '{q['anchor_text']}'")
            missing += 1
    if missing == 0:
        print("PASS: Toan bo 20/20 Anchor Texts deu khop hoan hao trong kho du lieu!")
    else:
        print(f"FAIL: Co {missing} cau hoi can dieu chinh lai anchor_text truoc khi do!\n")


def evaluate_mode(mode_func, questions: List[Dict[str, Any]], top_k: int = 5) -> Dict[str, Any]:
    hits_overall = 0
    mrr_overall = 0.0

    hits_late = 0
    mrr_late = 0.0
    count_late = 0

    hits_early = 0
    mrr_early = 0.0
    count_early = 0

    for q in questions:
        anchor_norm = normalize_text(q["anchor_text"])
        is_late = q.get("late_in_old_chunk", False)

        if is_late:
            count_late += 1
        else:
            count_early += 1

        results = mode_func(query=q["query"], ticker=q["ticker"], year=q.get("year", 2025), top_k=top_k)

        # Kiểm tra xem có chunk nào trong top_k chứa anchor không
        hit_rank = 0
        for rank, res in enumerate(results, start=1):
            if anchor_norm in normalize_text(res["text"]):
                hit_rank = rank
                break

        if hit_rank > 0:
            hits_overall += 1
            mrr_overall += 1.0 / hit_rank
            if is_late:
                hits_late += 1
                mrr_late += 1.0 / hit_rank
            else:
                hits_early += 1
                mrr_early += 1.0 / hit_rank

    n = len(questions)
    return {
        "overall": {
            "n": n,
            "hit@5": round(hits_overall / n, 4),
            "mrr": round(mrr_overall / n, 4)
        },
        "late_in_old_chunk (blind spot)": {
            "n": count_late,
            "hit@5": round(hits_late / count_late, 4) if count_late else 0,
            "mrr": round(mrr_late / count_late, 4) if count_late else 0
        },
        "early_in_old_chunk": {
            "n": count_early,
            "hit@5": round(hits_early / count_early, 4) if count_early else 0,
            "mrr": round(mrr_early / count_early, 4) if count_early else 0
        }
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default="eval_questions.json", help="Path to questions file")
    parser.add_argument("--label", default="baseline", help="Experiment label (e.g., baseline, token_chunked)")
    parser.add_argument("--outdir", default="results", help="Directory to save eval results")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    with open(args.questions, "r", encoding="utf-8") as f:
        questions = json.load(f)

    # 1. Validate anchors
    try:
        all_chunks = load_all_chunk_texts()
        check_anchors(questions, all_chunks)
    except NotImplementedError:
        print("Bo qua kiem tra anchor do chua noi load_all_chunk_texts.")

    print(f"\n[EVALUATION] Bat dau do dac danh gia cho nhan: [{args.label}] ...")

    results = {
        "label": args.label,
        "dense": evaluate_mode(dense_retrieve, questions),
        "bm25": evaluate_mode(bm25_retrieve, questions),
        "hybrid_rrf": evaluate_mode(hybrid_retrieve, questions)
    }

    out_file = os.path.join(args.outdir, f"retrieval_eval_{args.label}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 60)
    print(f"KET QUA DANH GIA RETRIEVAL [{args.label.upper()}]:")
    print("=" * 60)
    print(json.dumps(results, indent=2))
    print(f"\nDa luu ket qua tai: {out_file}")


if __name__ == "__main__":
    main()
