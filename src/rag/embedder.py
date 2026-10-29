"""Backward-compatibility forwarder for src.curated.embedder."""
from src.curated.embedder import *
from src.curated.embedder import build_vector_index

if __name__ == "__main__":
    build_vector_index()
