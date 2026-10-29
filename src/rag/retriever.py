"""Backward-compatibility forwarder for src.curated.retriever."""
import sys
from src.curated.retriever import *
from src.curated.retriever import rag_query, _build_prompt, _get_collection

if __name__ == "__main__":
    if len(sys.argv) > 1:
        rag_query(sys.argv[1])
    else:
        print("Sử dụng: python -m src.rag.retriever \"câu hỏi\"")
