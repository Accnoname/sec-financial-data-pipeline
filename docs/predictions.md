# Pre-Registered Hypotheses for Milestone 2 (Tokenizer-Aware Chunking)

**Date**: 2026-10-04  
**Author**: Engineering Team  
**Evaluation Harness**: 20 ground-truth questions on Form 10-K disclosures across 7 companies (AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA).

---

## 1. Context & Baseline Finding
In Milestone 1, baseline profiling on 500-word sliding window chunks revealed that **257 out of 262 chunks (98.1%)** exceeded the 256-token context limit of `all-MiniLM-L6-v2`. This created a silent truncation blind spot for text located at token index $>256$.

When evaluated on the 262-chunk baseline with metadata filtering:
- **Dense Only**: Overall Hit@5 = 14/20 (70.0%), Late (Blind Spot) Hit@5 = 6/10, Early Hit@5 = 8/10.
- **BM25 Only**: Overall Hit@5 = 18/20 (90.0%), Late Hit@5 = 9/10, Early Hit@5 = 9/10.
- **Hybrid (RRF $k=60$)**: Overall Hit@5 = 17/20 (85.0%), Late Hit@5 = 8/10, Early Hit@5 = 9/10.
- **Random Baseline (500 MC trials)**: Hit@1 = 0.8/20 (3.9%), Hit@5 = 3.6/20 (18.1%).

---

## 2. Pre-Registered Hypotheses (Prior to Running Milestone 2)

### Hypothesis 1 (H1: Dense Late-Chunk Recovery)
By enforcing a strict ceiling of $\le 220$ tokens (with 40-token overlap), 100% of chunks will fit within the 256-token embedding window. As a direct consequence, the dense embedding model will no longer be blind to text located in what was previously the second half of 500-word chunks.
- **Prediction**: Dense Hit@5 on the 10 "late" questions will increase from 6/10 in baseline.

### Hypothesis 2 (H2: Hybrid Alignment with BM25)
In Milestone 1, RRF consensus dynamics allowed a truncated Dense search to pull correct BM25 candidates out of Top-5 (e.g. Q1 and Q11). With Dense no longer blinded by truncation, Dense and BM25 signals should align better.
- **Prediction**: Hybrid will achieve Hit@1 $\ge$ BM25 and MRR $\ge$ BM25 on the new chunks (Note: This may be falsified if RRF still favors lexical matches over dense semantic candidates).

### Hypothesis 3 (H3: Token Budget Normalization & Pool Expansion Effect)
Chunking at $\le 220$ tokens will expand the total chunk pool by approximately 3–3.5x (from 262 to ~900+ chunks).
Because the retrieval pool is larger and each individual chunk contains less text (~170 tokens vs ~600 tokens):
- **Prediction A**: At $k=5$, absolute Hit@5 might see headwinds due to a harder pool and smaller text coverage per chunk (5 chunks $\approx 1,000$ tokens vs 3,000 tokens in baseline).
- **Prediction B**: When normalized for token budget at $k=15$ (~3,000 tokens total, matching 5 old chunks), retrieval rates will be substantially higher than at $k=5$.
