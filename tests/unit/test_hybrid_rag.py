"""
tests/unit/test_hybrid_rag.py: Unit tests for BM25 lexical search, RRF, and Hybrid Retriever.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.rag.bm25 import BM25Okapi, tokenize
from src.rag.hybrid_retriever import reciprocal_rank_fusion, HybridRetriever


def test_bm25_tokenization():
    """Verify that tokenization converts text to lowercase and strips common stopwords."""
    text = "The NVIDIA GPU supply chain in 2026 faces geopolitical risks and Taiwan constraints!"
    tokens = tokenize(text)
    
    # Assert stopwords like 'the', 'in', 'and' are removed
    assert "the" not in tokens
    assert "in" not in tokens
    assert "and" not in tokens
    
    # Assert important keywords are retained in lowercase
    assert "nvidia" in tokens
    assert "gpu" in tokens
    assert "supply" in tokens
    assert "chain" in tokens
    assert "2026" in tokens
    assert "taiwan" in tokens


def test_bm25_scoring_and_ranking():
    """Verify BM25 scores documents higher when query terms appear frequently and specifically."""
    docs = [
        {
            "chunk_id": "NVDA_0001",
            "text": "Nvidia faces semiconductor manufacturing bottlenecks at TSMC Taiwan foundries.",
            "metadata": {"ticker": "NVDA", "year": 2026},
        },
        {
            "chunk_id": "AAPL_0001",
            "text": "Apple develops custom silicon chips but relies on third party logistics and stores.",
            "metadata": {"ticker": "AAPL", "year": 2026},
        },
        {
            "chunk_id": "MSFT_0001",
            "text": "Microsoft operates hyperscale cloud data centers with substantial power consumption.",
            "metadata": {"ticker": "MSFT", "year": 2026},
        },
    ]

    bm25 = BM25Okapi(docs)
    results = bm25.search("TSMC Taiwan semiconductor", top_k=2)

    assert len(results) == 1
    assert results[0]["chunk_id"] == "NVDA_0001"
    assert results[0]["score"] > 0.0


def test_bm25_metadata_filtering():
    """Verify metadata filtering by ticker and year in BM25."""
    docs = [
        {"chunk_id": "NVDA_2025", "text": "Chip export controls", "metadata": {"ticker": "NVDA", "year": 2025}},
        {"chunk_id": "NVDA_2026", "text": "Chip export controls", "metadata": {"ticker": "NVDA", "year": 2026}},
        {"chunk_id": "AAPL_2026", "text": "Chip supply issues", "metadata": {"ticker": "AAPL", "year": 2026}},
    ]

    bm25 = BM25Okapi(docs)

    # Filter by NVDA and year 2026
    res = bm25.search("chip", top_k=5, ticker="NVDA", year=2026)
    assert len(res) == 1
    assert res[0]["chunk_id"] == "NVDA_2026"

    # Filter by ticker AAPL
    res_aapl = bm25.search("chip", top_k=5, ticker="AAPL")
    assert len(res_aapl) == 1
    assert res_aapl[0]["chunk_id"] == "AAPL_2026"


def test_reciprocal_rank_fusion_scoring():
    """Verify that RRF properly computes harmonic reciprocal ranks and rewards overlapping hits."""
    dense_results = [
        {"chunk_id": "DOC_A", "text": "Text A", "similarity": 0.95},
        {"chunk_id": "DOC_B", "text": "Text B", "similarity": 0.85},
        {"chunk_id": "DOC_C", "text": "Text C", "similarity": 0.75},
    ]
    bm25_results = [
        {"chunk_id": "DOC_B", "text": "Text B", "score": 8.5},
        {"chunk_id": "DOC_D", "text": "Text D", "score": 6.2},
        {"chunk_id": "DOC_A", "text": "Text A", "score": 3.1},
    ]

    # Formula with k=60:
    # DOC_A: Dense rank 1, BM25 rank 3 -> 1/(60+1) + 1/(60+3) = 1/61 + 1/63 = 0.016393 + 0.015873 = 0.032266
    # DOC_B: Dense rank 2, BM25 rank 1 -> 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.016129 + 0.016393 = 0.032522
    # DOC_C: Dense rank 3, BM25 None   -> 1/(60+3) = 1/63 = 0.015873
    # DOC_D: Dense None, BM25 rank 2   -> 1/(60+2) = 1/62 = 0.016129

    fused = reciprocal_rank_fusion(dense_results, bm25_results, k=60)

    assert len(fused) == 4
    # DOC_B should be #1 because rank 2 + rank 1 beats rank 1 + rank 3
    assert fused[0]["chunk_id"] == "DOC_B"
    assert pytest.approx(fused[0]["rrf_score"], abs=1e-5) == 0.032522

    # DOC_A should be #2
    assert fused[1]["chunk_id"] == "DOC_A"
    assert pytest.approx(fused[1]["rrf_score"], abs=1e-5) == 0.032266

    # DOC_D should be #3 (rank 2 beats rank 3)
    assert fused[2]["chunk_id"] == "DOC_D"

    # DOC_C should be #4
    assert fused[3]["chunk_id"] == "DOC_C"


def test_hybrid_retriever_pipeline():
    """Verify that HybridRetriever coordinates dense and sparse paths."""
    mock_bm25 = MagicMock(spec=BM25Okapi)
    mock_bm25.search.return_value = [
        {"chunk_id": "DOC_1", "text": "BM25 content", "metadata": {"ticker": "NVDA", "year": 2026}, "score": 5.0}
    ]

    with patch.object(HybridRetriever, "_dense_search") as mock_dense:
        mock_dense.return_value = [
            {"chunk_id": "DOC_1", "text": "Dense content", "metadata": {"ticker": "NVDA", "year": 2026}, "similarity": 0.9}
        ]

        retriever = HybridRetriever(bm25_index=mock_bm25)
        results = retriever.retrieve("test query", top_k=1)

        assert len(results) == 1
        assert results[0]["chunk_id"] == "DOC_1"
        assert results[0]["dense_rank"] == 1
        assert results[0]["bm25_rank"] == 1
        assert results[0]["rrf_score"] > 0.03
