"""
Tầng Gold (Aggregated & Feature Store Layer) trong Kiến trúc Medallion Lakehouse.
Bao gồm phân đoạn văn bản ngữ nghĩa (Semantic Chunking) ra Parquet Snappy và chỉ mục từ khóa BM25.
"""

from src.gold.chunking import (
    chunk_all_risk_factors,
    chunk_for_rag,
    split_into_chunks,
    get_tokenizer,
)
from src.gold.bm25 import (
    BM25Okapi,
    tokenize,
    load_bm25_index_from_parquet,
)

__all__ = [
    "chunk_all_risk_factors",
    "chunk_for_rag",
    "split_into_chunks",
    "get_tokenizer",
    "BM25Okapi",
    "tokenize",
    "load_bm25_index_from_parquet",
]
