"""Backward-compatibility forwarder for src.gold and src.curated."""
from src.gold import chunk_all_risk_factors, chunk_for_rag, split_into_chunks, BM25Okapi
from src.curated import build_vector_index, rag_query, HybridRetriever, reciprocal_rank_fusion

__all__ = [
    "chunk_all_risk_factors",
    "chunk_for_rag",
    "split_into_chunks",
    "BM25Okapi",
    "build_vector_index",
    "rag_query",
    "HybridRetriever",
    "reciprocal_rank_fusion",
]
