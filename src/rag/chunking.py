"""Backward-compatibility forwarder for src.gold.chunking."""
from src.gold.chunking import *
from src.gold.chunking import (
    chunk_all_risk_factors,
    chunk_for_rag,
    split_into_chunks,
    get_tokenizer,
)

if __name__ == "__main__":
    chunk_all_risk_factors()
