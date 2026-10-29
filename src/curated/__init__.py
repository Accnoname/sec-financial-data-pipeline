"""
Tầng Curated / Serving trong Kiến trúc Medallion Lakehouse.
Bao gồm tạo vector embeddings (ChromaDB), Semantic Retrieval, BM25 + Dense Hybrid Search (RRF), và Gemini AI RAG.
"""

from src.curated.embedder import build_vector_index
from src.curated.retriever import rag_query
from src.curated.hybrid_retriever import HybridRetriever, reciprocal_rank_fusion

__all__ = [
    "build_vector_index",
    "rag_query",
    "HybridRetriever",
    "reciprocal_rank_fusion",
]
