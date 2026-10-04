"""
benchmarks/evaluator.py: Benchmark Evaluation Suite for Retrieval (Dense vs BM25 vs Hybrid)

Evaluates Hit@5 and Mean Reciprocal Rank (MRR) on a 20-question ground-truth dataset.
"""

import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.hybrid_retriever import HybridRetriever


def run_benchmark(eval_file: Path | None = None, output_file: Path | None = None) -> dict:
    if eval_file is None:
        eval_file = PROJECT_ROOT / "benchmarks" / "evaluation_dataset.json"

    with open(eval_file, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"Loading HybridRetriever on current index...")
    retriever = HybridRetriever()

    results = {
        "dense": {"hits": 0, "reciprocal_ranks": [], "tail_hits": 0, "tail_count": 0},
        "bm25": {"hits": 0, "reciprocal_ranks": [], "tail_hits": 0, "tail_count": 0},
        "hybrid": {"hits": 0, "reciprocal_ranks": [], "tail_hits": 0, "tail_count": 0},
    }

    detailed_log = []

    for item in dataset:
        qid = item["id"]
        ticker = item["ticker"]
        query = item["query"]
        target_kw = item["keyword"].lower()
        is_tail = item.get("is_tail_target", False)

        # 1. Dense search
        dense_results = retriever._dense_search(
            query=query, candidate_count=5, ticker=ticker
        )

        # 2. BM25 search
        bm25_results = retriever.bm25_index.search(
            query=query, top_k=5, ticker=ticker
        )

        # 3. Hybrid search
        hybrid_results = retriever.retrieve(
            query=query, top_k=5, ticker=ticker
        )

        # Metric computation
        log_entry = {
            "id": qid,
            "ticker": ticker,
            "query": query,
            "keyword": target_kw,
            "is_tail": is_tail,
            "dense_rank": None,
            "bm25_rank": None,
            "hybrid_rank": None,
        }

        for mode, res_list in [("dense", dense_results), ("bm25", bm25_results), ("hybrid", hybrid_results)]:
            if is_tail:
                results[mode]["tail_count"] += 1

            matched_rank = None
            for rank_idx, r in enumerate(res_list, 1):
                if target_kw in r["text"].lower():
                    matched_rank = rank_idx
                    break

            if matched_rank is not None:
                results[mode]["hits"] += 1
                results[mode]["reciprocal_ranks"].append(1.0 / matched_rank)
                if is_tail:
                    results[mode]["tail_hits"] += 1
                log_entry[f"{mode}_rank"] = matched_rank
            else:
                results[mode]["reciprocal_ranks"].append(0.0)

        detailed_log.append(log_entry)

    total_q = len(dataset)
    summary = {
        "total_questions": total_q,
        "dense_hit_at_5": results["dense"]["hits"] / total_q,
        "dense_mrr": sum(results["dense"]["reciprocal_ranks"]) / total_q,
        "dense_tail_hit_at_5": results["dense"]["tail_hits"] / max(results["dense"]["tail_count"], 1),
        "bm25_hit_at_5": results["bm25"]["hits"] / total_q,
        "bm25_mrr": sum(results["bm25"]["reciprocal_ranks"]) / total_q,
        "bm25_tail_hit_at_5": results["bm25"]["tail_hits"] / max(results["bm25"]["tail_count"], 1),
        "hybrid_hit_at_5": results["hybrid"]["hits"] / total_q,
        "hybrid_mrr": sum(results["hybrid"]["reciprocal_ranks"]) / total_q,
        "hybrid_tail_hit_at_5": results["hybrid"]["tail_hits"] / max(results["hybrid"]["tail_count"], 1),
        "detailed_log": detailed_log,
    }

    # Print summary table
    print("\n" + "=" * 70)
    print(f"RETRIEVAL BENCHMARK RESULTS ({total_q} questions)")
    print("=" * 70)
    print(f"{'Configuration':<25} | {'Hit@5':<10} | {'MRR':<10} | {'Tail Hit@5 (>220 tok)':<20}")
    print("-" * 70)
    print(f"{'Dense Only (ChromaDB)':<25} | {summary['dense_hit_at_5']*100:>6.1f}%   | {summary['dense_mrr']:>6.3f}   | {summary['dense_tail_hit_at_5']*100:>6.1f}%")
    print(f"{'Sparse Only (BM25)':<25} | {summary['bm25_hit_at_5']*100:>6.1f}%   | {summary['bm25_mrr']:>6.3f}   | {summary['bm25_tail_hit_at_5']*100:>6.1f}%")
    print(f"{'Hybrid (Dense + BM25)':<25} | {summary['hybrid_hit_at_5']*100:>6.1f}%   | {summary['hybrid_mrr']:>6.3f}   | {summary['hybrid_tail_hit_at_5']*100:>6.1f}%")
    print("=" * 70)

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Results saved to {output_file}")

    return summary


if __name__ == "__main__":
    out_name = sys.argv[1] if len(sys.argv) > 1 else "optimized_eval_results.json"
    out_target = PROJECT_ROOT / "benchmarks" / out_name
    run_benchmark(output_file=out_target)
