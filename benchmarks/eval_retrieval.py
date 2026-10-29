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
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.config import GOLD_DIR
from src.curated.hybrid_retriever import HybridRetriever

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
    parquet_path = GOLD_DIR / "chunks" / "all_chunks.parquet"
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
    pool_size = max(30, top_k * 2)
    results = retriever.retrieve(
        query=query,
        top_k=top_k,
        candidate_pool_size=pool_size,
        ticker=ticker,
        year=year,
    )
    if not results and year:
        results = retriever.retrieve(
            query=query,
            top_k=top_k,
            candidate_pool_size=pool_size,
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


def compute_random_baseline(questions: List[Dict[str, Any]], all_chunks: List[Dict[str, Any]], num_trials: int = 500) -> Dict[str, Any]:
    """Tính random baseline qua mô phỏng Monte Carlo trên pool sau khi lọc ticker+year."""
    import random
    random.seed(42)
    
    hits_1 = 0
    hits_5 = 0
    hits_15 = 0
    mrr_total = 0.0
    total_runs = num_trials * len(questions)

    for _ in range(num_trials):
        for q in questions:
            t = q["ticker"]
            y = q["year"]
            anchor_norm = normalize_text(q["anchor_text"])
            pool = [c for c in all_chunks if c.get("ticker") == t and c.get("year") == y]
            if not pool:
                pool = [c for c in all_chunks if c.get("ticker") == t]
            
            sampled = random.sample(pool, min(15, len(pool)))
            hit_rank = 0
            for rank, c in enumerate(sampled, 1):
                if anchor_norm in normalize_text(c["text"]):
                    hit_rank = rank
                    break
            
            if hit_rank == 1:
                hits_1 += 1
            if 1 <= hit_rank <= 5:
                hits_5 += 1
            if 1 <= hit_rank <= 15:
                hits_15 += 1
            if hit_rank > 0:
                mrr_total += 1.0 / hit_rank

    return {
        "trials": num_trials,
        "hit@1": round(hits_1 / total_runs, 4),
        "hit@5": round(hits_5 / total_runs, 4),
        "hit@15": round(hits_15 / total_runs, 4),
        "mrr": round(mrr_total / total_runs, 4),
    }


def evaluate_mode(mode_func, questions: List[Dict[str, Any]], top_k: int = 15) -> Dict[str, Any]:
    hits_1_overall = 0
    hits_5_overall = 0
    hits_15_overall = 0
    mrr_overall = 0.0

    hits_1_late = 0
    hits_5_late = 0
    hits_15_late = 0
    mrr_late = 0.0
    count_late = 0

    hits_1_early = 0
    hits_5_early = 0
    hits_15_early = 0
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
            mrr_overall += 1.0 / hit_rank
            if hit_rank == 1:
                hits_1_overall += 1
            if hit_rank <= 5:
                hits_5_overall += 1
            if hit_rank <= 15:
                hits_15_overall += 1

            if is_late:
                mrr_late += 1.0 / hit_rank
                if hit_rank == 1:
                    hits_1_late += 1
                if hit_rank <= 5:
                    hits_5_late += 1
                if hit_rank <= 15:
                    hits_15_late += 1
            else:
                mrr_early += 1.0 / hit_rank
                if hit_rank == 1:
                    hits_1_early += 1
                if hit_rank <= 5:
                    hits_5_early += 1
                if hit_rank <= 15:
                    hits_15_early += 1

    n = len(questions)
    return {
        "overall": {
            "n": n,
            "hit@1": f"{hits_1_overall}/{n} ({round(hits_1_overall / n, 4)})",
            "hit@5": round(hits_5_overall / n, 4),
            "hit@5_count": f"{hits_5_overall}/{n}",
            "hit@15": round(hits_15_overall / n, 4),
            "hit@15_count": f"{hits_15_overall}/{n}",
            "mrr": round(mrr_overall / n, 4)
        },
        "late_in_old_chunk (blind spot)": {
            "n": count_late,
            "hit@1": f"{hits_1_late}/{count_late} ({round(hits_1_late / count_late, 4) if count_late else 0})",
            "hit@5": round(hits_5_late / count_late, 4) if count_late else 0,
            "hit@5_count": f"{hits_5_late}/{count_late}",
            "hit@15": round(hits_15_late / count_late, 4) if count_late else 0,
            "hit@15_count": f"{hits_15_late}/{count_late}",
            "mrr": round(mrr_late / count_late, 4) if count_late else 0
        },
        "early_in_old_chunk": {
            "n": count_early,
            "hit@1": f"{hits_1_early}/{count_early} ({round(hits_1_early / count_early, 4) if count_early else 0})",
            "hit@5": round(hits_5_early / count_early, 4) if count_early else 0,
            "hit@5_count": f"{hits_5_early}/{count_early}",
            "hit@15": round(hits_15_early / count_early, 4) if count_early else 0,
            "hit@15_count": f"{hits_15_early}/{count_early}",
            "mrr": round(mrr_early / count_early, 4) if count_early else 0
        }
    }


def main():
    default_questions = Path(__file__).resolve().parent / "eval_questions.json"
    if not default_questions.exists():
        default_questions = PROJECT_ROOT / "eval_questions.json"

    default_outdir = PROJECT_ROOT / "results"

    parser = argparse.ArgumentParser(description="Evaluate Dense, BM25, and Hybrid Retrieval on SEC 10-K Chunks.")
    parser.add_argument("--questions", default=str(default_questions), help="Path to questions file")
    parser.add_argument("--label", default="tokenaware", help="Experiment label (e.g., baseline, tokenaware)")
    parser.add_argument("--outdir", default=str(default_outdir), help="Directory to save eval results")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    with open(args.questions, "r", encoding="utf-8") as f:
        questions = json.load(f)

    # 1. Validate anchors
    all_chunks = load_all_chunk_texts()
    check_anchors(questions, all_chunks)

    # 2. Random baseline for current pool
    random_base = compute_random_baseline(questions, all_chunks)
    print(f"\n[RANDOM BASELINE] Pool trung binh: {len(all_chunks)/7:.1f} chunks/ticker")
    print(f"   Random Hit@1:  {random_base['hit@1'] * 100:.2f}%")
    print(f"   Random Hit@5:  {random_base['hit@5'] * 100:.2f}%")
    print(f"   Random Hit@15: {random_base['hit@15'] * 100:.2f}%")
    print(f"   Random MRR:    {random_base['mrr']:.4f}")

    print(f"\n[EVALUATION] Bat dau do dac danh gia cho nhan: [{args.label}] (k=5 va k=15) ...")

    results = {
        "label": args.label,
        "total_chunks_in_pool": len(all_chunks),
        "random_baseline": random_base,
        "dense": evaluate_mode(dense_retrieve, questions, top_k=15),
        "bm25": evaluate_mode(bm25_retrieve, questions, top_k=15),
        "hybrid_rrf": evaluate_mode(hybrid_retrieve, questions, top_k=15)
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
