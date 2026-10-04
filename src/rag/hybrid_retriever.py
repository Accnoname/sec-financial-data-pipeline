"""
src/rag/hybrid_retriever.py: Hybrid Search Retriever combining BM25 and Dense Vectors via RRF.

Combines sparse lexical search (BM25) and dense semantic search (ChromaDB embeddings)
using Reciprocal Rank Fusion (RRF) to maximize retrieval precision and recall across
SEC Form 10-K financial filings.
"""

import os
import sys
import logging
import warnings
from typing import Any

# Silence noisy external library loggers
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
for noisy_mod in ("httpx", "sentence_transformers", "huggingface_hub", "transformers", "chromadb", "urllib3"):
    logging.getLogger(noisy_mod).setLevel(logging.ERROR)

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from src.common.config import CURATED_DIR, PRIMARY_DIR
from src.common.logger import get_logger
from src.rag.bm25 import BM25Okapi, load_bm25_index_from_parquet

logger = get_logger("hybrid_retriever")

COLLECTION_NAME = "sec_risk_factors"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RRF_SMOOTHING_K = 60


def reciprocal_rank_fusion(
    dense_results: list[dict],
    bm25_results: list[dict],
    k: int = RRF_SMOOTHING_K,
    weight_dense: float = 1.0,
    weight_bm25: float = 1.0,
) -> list[dict]:
    """
    Merges dense and sparse search results using Reciprocal Rank Fusion (RRF).

    Formula:
      RRF_Score(d) = (weight_dense / (k + rank_dense(d))) + (weight_bm25 / (k + rank_bm25(d)))
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}
    dense_ranks: dict[str, int] = {}
    dense_sims: dict[str, float] = {}
    bm25_ranks: dict[str, int] = {}
    bm25_scores: dict[str, float] = {}

    # Process Dense results
    for rank, item in enumerate(dense_results, start=1):
        cid = item["chunk_id"]
        doc_map[cid] = item
        dense_ranks[cid] = rank
        dense_sims[cid] = item.get("similarity", 0.0)
        scores[cid] = scores.get(cid, 0.0) + (weight_dense / (k + rank))

    # Process BM25 results
    for rank, item in enumerate(bm25_results, start=1):
        cid = item["chunk_id"]
        if cid not in doc_map:
            doc_map[cid] = item
        bm25_ranks[cid] = rank
        bm25_scores[cid] = item.get("score", 0.0)
        scores[cid] = scores.get(cid, 0.0) + (weight_bm25 / (k + rank))

    # Sort items descending by combined RRF score
    sorted_cids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    fused_results = []
    for cid in sorted_cids:
        raw_item = doc_map[cid]
        fused_results.append({
            "chunk_id": cid,
            "text": raw_item["text"],
            "metadata": raw_item.get("metadata", {}),
            "rrf_score": round(scores[cid], 6),
            "dense_rank": dense_ranks.get(cid, None),
            "dense_similarity": dense_sims.get(cid, None),
            "bm25_rank": bm25_ranks.get(cid, None),
            "bm25_score": bm25_scores.get(cid, None),
        })

    return fused_results


class HybridRetriever:
    """
    Executes hybrid retrieval over SEC 10-K chunks using ChromaDB and BM25.
    """

    def __init__(
        self,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
        bm25_index: BM25Okapi | None = None,
    ):
        self.embedding_model_name = embedding_model_name
        self.encoder = SentenceTransformer(embedding_model_name)
        self.bm25_index = bm25_index or load_bm25_index_from_parquet()
        self._collection = None

    @property
    def collection(self) -> chromadb.Collection:
        """Lazily connects to the ChromaDB vector database."""
        if self._collection is None:
            vector_db_path = CURATED_DIR / "vector_db"
            if not vector_db_path.exists():
                raise FileNotFoundError(
                    f"Vector DB directory not found at '{vector_db_path}'. Run Step 6 first: python run.py 6"
                )
            client = chromadb.PersistentClient(
                path=str(vector_db_path),
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = client.get_collection(COLLECTION_NAME)
        return self._collection

    def _dense_search(
        self,
        query: str,
        candidate_count: int,
        ticker: str | None = None,
        year: int | None = None,
    ) -> list[dict]:
        """Performs dense semantic vector search via ChromaDB."""
        query_vector = self.encoder.encode([query], show_progress_bar=False)[0].tolist()

        where_filter: dict[str, Any] | None = None
        if ticker and year:
            where_filter = {"$and": [{"ticker": ticker.upper()}, {"year": int(year)}]}
        elif ticker:
            where_filter = {"ticker": ticker.upper()}
        elif year:
            where_filter = {"year": int(year)}

        query_kwargs: dict[str, Any] = {
            "query_embeddings": [query_vector],
            "n_results": candidate_count,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = self.collection.query(**query_kwargs)
        if not results or not results["documents"] or not results["documents"][0]:
            return []

        dense_items = []
        for cid, doc, meta, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = round(1.0 - dist, 4)
            dense_items.append({
                "chunk_id": cid,
                "text": doc,
                "metadata": meta,
                "similarity": similarity,
            })
        return dense_items

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        candidate_pool_size: int = 15,
        ticker: str | None = None,
        year: int | None = None,
        weight_dense: float = 1.0,
        weight_bm25: float = 1.0,
    ) -> list[dict]:
        """
        Retrieves top_k relevant chunks using dual-path retrieval and RRF rank fusion.
        
        1. Retrieves candidate_pool_size chunks via dense vector search.
        2. Retrieves candidate_pool_size chunks via BM25 lexical search.
        3. Merges and re-ranks via Reciprocal Rank Fusion.
        4. Returns top_k highest-scoring unified chunks.
        """
        dense_candidates = self._dense_search(
            query=query,
            candidate_count=candidate_pool_size,
            ticker=ticker,
            year=year,
        )

        bm25_candidates = self.bm25_index.search(
            query=query,
            top_k=candidate_pool_size,
            ticker=ticker,
            year=year,
        )

        fused_results = reciprocal_rank_fusion(
            dense_results=dense_candidates,
            bm25_results=bm25_candidates,
            k=RRF_SMOOTHING_K,
            weight_dense=weight_dense,
            weight_bm25=weight_bm25,
        )

        return fused_results[:top_k]
