"""Backward-compatibility forwarder for src.gold.bm25."""
from src.gold.bm25 import *
from src.gold.bm25 import (
    BM25Okapi,
    tokenize,
    load_bm25_index_from_parquet,
)
