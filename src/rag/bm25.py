"""
src/rag/bm25.py: Pure Python Okapi BM25 implementation for lexical keyword retrieval.

Provides BM25 ranking for financial text chunks without external library dependencies,
enabling exact keyword matching, statutory term lookup, and lexical scoring.
"""

import math
import re
from collections import Counter
from pathlib import Path
import pandas as pd

from src.common.config import PRIMARY_DIR
from src.common.logger import get_logger

logger = get_logger("bm25_search")

# Compact set of common English stopwords to reduce noise in frequency calculation
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than",
    "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's",
    "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom",
    "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll",
    "you're", "you've", "your", "yours", "yourself", "yourselves"
}


def tokenize(text: str) -> list[str]:
    """
    Tokenizes text into lowercase alphanumeric words, stripping punctuation.
    Filters out common stopwords.
    """
    if not text:
        return []
    words = re.findall(r"\b[a-zA-Z0-9_\$]+\b", text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


class BM25Okapi:
    """
    Okapi BM25 implementation for lexical keyword search.
    
    Formula:
      IDF(q) = ln((N - n(q) + 0.5) / (n(q) + 0.5) + 1.0)
      Score(D, Q) = sum( IDF(q) * (f(q, D) * (k1 + 1)) / (f(q, D) + k1 * (1 - b + b * (|D| / avgdl))) )
    """

    def __init__(self, documents: list[dict], k1: float = 1.5, b: float = 0.75):
        """
        Initializes the BM25 index with a list of document dicts.
        Each document must contain 'chunk_id', 'text', and 'metadata'.
        """
        self.k1 = k1
        self.b = b
        self.documents = documents
        self.doc_count = len(documents)
        
        self.doc_tokens: list[list[str]] = []
        self.doc_lengths: list[int] = []
        self.doc_freqs: list[Counter] = []
        self.df: dict[str, int] = Counter()
        self.idf: dict[str, float] = {}

        self._build_index()

    def _build_index(self) -> None:
        """Computes token frequencies, document lengths, and inverse document frequencies."""
        total_length = 0
        for doc in self.documents:
            tokens = tokenize(doc.get("text", ""))
            self.doc_tokens.append(tokens)
            doc_len = len(tokens)
            self.doc_lengths.append(doc_len)
            total_length += doc_len
            
            tf = Counter(tokens)
            self.doc_freqs.append(tf)
            for term in tf.keys():
                self.df[term] = self.df.get(term, 0) + 1

        self.avgdl = (total_length / self.doc_count) if self.doc_count > 0 else 0.0

        # Calculate smooth IDF for each term in vocabulary
        for term, freq in self.df.items():
            self.idf[term] = math.log((self.doc_count - freq + 0.5) / (freq + 0.5) + 1.0)

    def search(
        self,
        query: str,
        top_k: int = 10,
        ticker: str | None = None,
        year: int | None = None,
    ) -> list[dict]:
        """
        Scores all indexed documents against query terms and returns top_k documents.
        Supports metadata filtering by ticker and year.
        """
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores: list[tuple[int, float]] = []

        for idx, doc in enumerate(self.documents):
            meta = doc.get("metadata", {})
            if ticker and meta.get("ticker", "").upper() != ticker.upper():
                continue
            if year and int(meta.get("year", 0)) != int(year):
                continue

            doc_len = self.doc_lengths[idx]
            if doc_len == 0 or self.avgdl == 0:
                continue

            tf_dict = self.doc_freqs[idx]
            doc_score = 0.0

            for q_term in query_tokens:
                if q_term not in tf_dict:
                    continue
                tf = tf_dict[q_term]
                idf_val = self.idf.get(q_term, 0.0)
                
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                doc_score += idf_val * (numerator / denominator)

            if doc_score > 0:
                scores.append((idx, doc_score))

        # Sort descending by score
        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scores[:top_k]:
            doc_item = self.documents[idx]
            results.append({
                "chunk_id": doc_item["chunk_id"],
                "text": doc_item["text"],
                "metadata": doc_item.get("metadata", {}),
                "score": round(score, 4),
            })

        return results


def load_bm25_index_from_parquet(parquet_path: Path | None = None) -> BM25Okapi:
    """Loads chunks from the Gold parquet file and builds a BM25Okapi index."""
    if parquet_path is None:
        parquet_path = PRIMARY_DIR / "chunks" / "all_chunks.parquet"

    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Gold chunks parquet not found at '{parquet_path}'. Run Step 5 first: python run.py 5"
        )

    df = pd.read_parquet(parquet_path)
    documents = []
    for _, row in df.iterrows():
        documents.append({
            "chunk_id": row["chunk_id"],
            "text": row["text"],
            "metadata": {
                "ticker": row["ticker"],
                "year": int(row["year"]),
                "section": row["section"],
                "chunk_index": int(row["chunk_index"]),
                "total_chunks": int(row["total_chunks"]),
                "word_count": int(row["word_count"]),
            }
        })

    logger.info(f"Loaded {len(documents)} chunks into BM25 index from {parquet_path.name}")
    return BM25Okapi(documents)
