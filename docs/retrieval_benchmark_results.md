# Empirical Retrieval Benchmark: Dense vs Sparse (BM25) vs Hybrid Search

## 1. Executive Summary & Root Cause Analysis

### The Discovery: Silent Truncation Bug in Local Embedding
During an internal audit of token sequence lengths in the Gold and Curated tiers of the SEC Financial Lakehouse, empirical token profiling revealed a critical architectural mismatch:
- The local embedding model (`sentence-transformers/all-MiniLM-L6-v2`) enforces a strict sequence window of `max_seq_length = 256 tokens`.
- The legacy sliding-window chunking implementation used 500 English words per chunk with a 100-word overlap.
- Profiling of all 262 legacy chunks revealed an average length of **596.3 tokens** (ranging up to 679 tokens).
- **98.1% of chunks (257 out of 262)** exceeded the 256-token ceiling.
- Because `SentenceTransformer` silently truncates input sequences without raising exceptions, more than **57% of narrative risk text per chunk was discarded in dense vector space**, and the 100-word overlap window at the tail of each chunk was completely severed.
- In contrast, sparse BM25 lexical search tokenized the full text string without length truncation, causing a severe information asymmetry between dense and sparse index representations.

### The Engineering Resolution
1. **Tokenizer-Aware Sliding-Window Chunking (Approach A)**:
   - Replaced fixed word-count slicing with a sentence-aware, tokenizer-driven sliding window (`BertTokenizerFast`).
   - Slices text at punctuation boundaries targeting 210 tokens with a 40-token overlap, guarded by a hard ceiling of 240 tokens.
   - Guaranteed that **100.0% of chunks (925 total chunks across 7 public companies)** strictly conform to $\le 256$ tokens (mean = 175.1 tokens, max = 233 tokens).
2. **Deterministic Idempotent Re-indexing**:
   - Dropped and recreated the ChromaDB collection (`sec_risk_factors`) to eliminate orphaned vectors caused by the expansion from 262 to 925 deterministic chunk IDs.
3. **Automated Data Contract Gate**:
   - Added `test_gold_chunks_fit_embedding_context_window` into `tests/test_pipeline.py` to assert that zero chunks exceed the embedding model's context window.

---

## 2. Empirical Benchmark Methodology

To evaluate retrieval efficacy, a ground-truth dataset of **20 realistic financial risk queries** was constructed across the 7 tech conglomerates (AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA), mapped to disclosures in Form 10-K Item 1A.

Crucially, **18 of the 20 queries (90%) targeted topics originally located in the second half of chunks (token index > 220)**, specifically testing retrieval performance across the boundary where the dense model previously suffered silent truncation.

Evaluation Metrics:
- **Hit@5**: Proportion of queries where the relevant ground-truth chunk is retrieved in the top 5 candidates.
- **MRR (Mean Reciprocal Rank)**: $\frac{1}{|Q|} \sum_{q=1}^{|Q|} \frac{1}{\text{rank}(q)}$, rewarding systems that position the correct result closer to rank 1.
- **Tail Hit@5**: Hit rate specifically on the 18 queries targeting disclosures beyond token index 220.

---

## 3. Before vs. After Benchmark Results

### Evaluation on 20 Ground-Truth Financial Risk Queries

| Configuration | Metric | Before (500 Words, 262 Chunks) | After (Tokenizer-Aware, 925 Chunks) | Absolute Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Dense Only (ChromaDB)** | **Hit@5** | **25.0%** (5/20) | **85.0%** (17/20) | **+60.0%** |
| | **MRR** | **0.138** | **0.660** | **+0.522 (4.8x)** |
| | **Tail Hit@5 (>220 tok)** | **22.2%** (4/18) | **83.3%** (15/18) | **+61.1%** |
| **Sparse Only (BM25)** | **Hit@5** | **30.0%** (6/20) | **85.0%** (17/20) | **+55.0%** |
| | **MRR** | **0.162** | **0.775** | **+0.613 (4.8x)** |
| | **Tail Hit@5 (>220 tok)** | **33.3%** (6/18) | **88.9%** (16/18) | **+55.6%** |
| **Hybrid (Dense + BM25, RRF k=60)** | **Hit@5** | **30.0%** (6/20) | **90.0%** (18/20) | **+60.0% (3.0x)** |
| | **MRR** | **0.133** | **0.779** | **+0.646 (5.8x)** |
| | **Tail Hit@5 (>220 tok)** | **33.3%** (6/18) | **88.9%** (16/18) | **+55.6%** |

---

## 4. Key Engineering Insights

1. **Information Completeness Over Chunk Size**:
   - Larger chunks (500 words) diluted semantic vectors and caused silent truncation.
   - Granular, sentence-bounded chunks (175 tokens mean) drastically increased vector specificity, leading to a jump from 25% to 85% in dense Hit@5.
2. **Complementarity of Hybrid Search**:
   - While dense and sparse methods each scored 85.0% Hit@5 individually, Reciprocal Rank Fusion (RRF) fused orthogonal signals:
     - Exact terminology (e.g. `TSMC`, `OpenAI`, `Item 1A`, `Reality Labs`) anchored by BM25.
     - Conceptual paraphrasing (e.g. `foundry reliance`, `loss of ad tracking signal`) captured by Dense search.
   - The unified Hybrid retrieval achieved **90.0% Hit@5** and a top-tier **MRR of 0.779**.

---

## 5. Tailored Interview Talking Points & Resume Bullets

### Production Resume Bullet:
> "Discovered via token profiling that 98% of 500-word chunks exceeded the 256-token context limit of `all-MiniLM-L6-v2`, silently degrading dense retrieval; re-engineered the pipeline to tokenizer-aware sentence chunking (mean 175 tokens, 0% truncated) and implemented hybrid retrieval (BM25 + ChromaDB with RRF), boosting Hit@5 from 25% to 85% (dense) and 90% (hybrid) across a 20-query evaluation set. Enforced a pytest Data Contract preventing context window overflow."

### Technical Interview Defense:
- **Interviewer**: *"Tell me about a difficult silent bug you caught in your data pipeline."*
- **Response**: *"In our SEC EDGAR Lakehouse, the initial pipeline executed smoothly without errors because SentenceTransformer defaults to silent truncation. By profiling token lengths against the model's 256-token context limit, I found 98.1% of our 500-word chunks were truncated, losing over 57% of text and severing the chunk overlap in dense vector space. I built a 20-query benchmark targeting tail disclosures to measure the baseline (Hit@5 was only 25%), refactored the chunker to be tokenizer-aware (<240 tokens), purged and re-indexed ChromaDB to avoid orphaned vectors, and lifted Hit@5 to 85% dense and 90% hybrid (MRR 0.779). Finally, I codified a pytest data contract to assert all chunks fit within the context limit."*
