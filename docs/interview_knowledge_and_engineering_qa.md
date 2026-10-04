# Data Engineering Interview Knowledge & Architecture Defense Q&A

This document records the technical interview questions, candidate responses, model senior responses, and comprehensive architectural glossaries derived from the SEC Financial Data Pipeline and RAG System.

---

## 1. Storage Architecture & Columnar Formats

### Interviewer Question
> "In this project, data flows through a Medallion Lakehouse architecture, converting raw HTML and JSON disclosures into Snappy-compressed Parquet files at the Silver and Gold tiers.
> 1. Why did you select Parquet instead of CSV or JSON?
> 2. From the perspective of physical disk storage and analytical query performance (OLAP), how does columnar storage optimize disk I/O and CPU utilization?"

### Candidate's Original Response & Core Intuition
- **Core Understanding:** Parquet reduces data read volume, speeds up analytical queries, provides higher compression ratios, and its columnar structure speeds up value retrieval while reducing CPU compute overhead.
- **Evaluation:** Strong technical intuition. The core rationale (I/O reduction and compression efficiency) is correct. Needs enhancement with standard industry terminology (Column Projection and Predicate Pushdown).

### Senior Engineering Model Answer
> "We chose Apache Parquet over row-oriented formats (CSV/JSON) for three architectural reasons:
> 
> First, for storage efficiency: Parquet organizes values by column rather than by row. Because values in the same column share identical data types and often repeating patterns, encoders like Dictionary Encoding and Run-Length Encoding (RLE) combined with Snappy achieve over 70% disk compression compared to raw JSON.
> 
> Second, for OLAP read performance: Parquet enables **Column Projection**. Analytical queries rarely select every column. In Parquet, the query engine seeks directly to the byte ranges of requested columns (e.g., `ticker`, `word_count`) and skips heavy narrative text columns entirely, reducing Disk I/O by 80-90%.
> 
> Third, for compute optimization: Parquet files contain metadata in their file footers, recording `min` and `max` statistics for each data block. Through **Predicate Pushdown**, queries filtering on `WHERE year = 2026` can inspect the footer and discard entire files without reading their row data into RAM."

### Deep-Dive Terminology Glossary

#### Column Projection
- **Definition:** The ability of a storage format and query engine to read only the specific columns requested by a query (e.g., `SELECT ticker, word_count FROM table`) without loading unrequested columns from disk.
- **Physical Mechanism:** In row-oriented files (CSV/JSON), fields for a record are stored sequentially (`val1, val2, val3\n`). The disk read head must traverse the entire line to reach the last field. In Parquet, all values of `col1` are stored contiguously in a Data Page, followed by `col2`. The reader computes byte offsets and reads only the target pages.

#### Predicate Pushdown
- **Definition:** An optimization technique where filtering conditions (predicates, such as `WHERE ticker = 'NVDA'`) are evaluated directly at the storage layer prior to loading data into compute memory.
- **Physical Mechanism:** Every Parquet file contains a FileMetaData footer storing column chunk metadata, dictionary page offsets, and data statistics (`min_value`, `max_value`, `null_count`). When a query runs, the execution engine reads the footer first. If the target value falls outside the `[min, max]` range of a block, that block is skipped entirely without decompression or memory allocation.

#### Dictionary Encoding
- **Definition:** A lossless compression technique that replaces repetitive data values with small integer keys.
- **Example:** If the string `'AAPL'` (4 bytes) appears 1,000,000 times in a column, storing it raw consumes 4 MB. With Dictionary Encoding, a small dictionary maps `0 -> 'AAPL'`, and the column stores integer `0` (often packed into 1-2 bits), reducing memory footprint by over 80%.

#### Run-Length Encoding (RLE)
- **Definition:** A compression algorithm that stores consecutive repeated values as a single data value and a count.
- **Example:** In a sorted dataset containing 10,000 consecutive instances of year `2026`, RLE records `(2026, 10000)`. This transforms tens of kilobytes into a single integer tuple.

#### Snappy Compression
- **Definition:** A byte-oriented compression algorithm developed by Google, engineered specifically for high throughput rather than maximum compression ratio.
- **Trade-off Analysis:** While algorithms like Gzip or Bzip2 achieve slightly higher compression ratios, their decompression cycle consumes significant CPU time. Snappy decompresses at rates exceeding 250-500 MB/s per CPU core, ensuring decompression never becomes the pipeline's computational bottleneck.

---

## 2. Pipeline Orchestration, Sensors & Idempotency

### Interviewer Question
> "Form 10-K filings are submitted once per year per company. If your pipeline is scheduled to execute automatically at 02:00 AM daily:
> 1. How does the system determine whether a new filing exists without downloading massive multi-megabyte HTML files?
> 2. What does Idempotency mean in Data Engineering, and if a pipeline task retries three times due to intermittent network failures, how do you guarantee zero data duplication?"

### Candidate's Original Response & Core Intuition
- **Core Understanding:** The pipeline sends lightweight requests to inspect whether a new report exists and terminates downstream tasks if no changes are found. Defined idempotency accurately as: *"Performing an operation multiple times leaves the system in the same state as the initial execution."* Confirmed that retried tasks do not duplicate data.
- **Evaluation:** Outstanding grasp of the mathematical definition of Idempotency ($f(f(x)) = f(x)$). Needs explicit clarification on how Deterministic Naming and Atomic Overwrites physically prevent disk duplication.

### Senior Engineering Model Answer
> "To prevent resource waste during daily 02:00 AM scheduled runs, we implement a **Sensor and High-Water Mark pattern** at Step 3:
> 
> Rather than downloading 8 MB HTML files, the sensor issues a lightweight HTTP GET request to the SEC EDGAR submissions endpoint (`https://data.sec.gov/submissions/CIK{cik}.json`), fetching a ~5 KB JSON payload containing filing metadata. The sensor extracts the latest `accessionNumber` and compares it to the local `metadata.json` record. If the accession matches, the DAG short-circuits downstream tasks, completing the daily verification in under 4 seconds with zero compute or API token waste.
> 
> Regarding **Idempotency**, an operation is idempotent if running it once or ten times produces identical state. In this pipeline, idempotency is guaranteed through **Deterministic Naming** and **Atomic Overwrite**:
> 
> Every output artifact has a fixed business key path (e.g., `data/03_primary/chunks/NVDA_2026_chunks.parquet`). If network dropout forces a task to retry three times, each retry writes directly over the same target file path. Because we never use execution timestamps in file names and avoid append-only operations without deduplication, duplicate records are mathematically eliminated."

### Deep-Dive Terminology Glossary

#### Metadata vs. Payload Data
- **Payload Data:** The actual content payload (e.g., the complete 8 MB Form 10-K HTML document containing Item 1A, financial tables, and legal disclosures).
- **Metadata:** Data describing the payload (e.g., `filingDate: 2026-02-25`, `accessionNumber: 0001045810-26-000021`, document file name, and file byte size).
- **Cost Differential:** Fetching metadata costs ~5 KB of network transfer and ~100 ms of latency; fetching raw payload costs 2-8 MB and seconds of transfer time. Checking metadata first is the foundation of change detection.

#### SEC Accession Number
- **Definition:** A unique 20-character alphanumeric identifier assigned by the SEC EDGAR system to every filing submitted by a registrant.
- **Structure:** `0000320193-25-000079`
  - `0000320193`: Central Index Key (CIK) of the company (Apple Inc.).
  - `25`: Filing year (2025).
  - `000079`: Sequential filing counter assigned by SEC for that year.
- **Engineering Role:** Serves as the natural primary key and high-water mark for SEC disclosure ingestion.

#### Sensor Pattern & Short-Circuit Execution
- **Sensor:** A lightweight polling task whose sole responsibility is to evaluate an external precondition (e.g., file availability, API version change, partition arrival) without executing heavy processing.
- **Short-Circuit Execution:** When a sensor evaluates to `false` (no new data detected), the DAG immediately terminates or transitions downstream dependent tasks to `SKIPPED` status, avoiding execution of downstream transformation and model stages.

#### Deterministic Naming vs. Non-Deterministic Timestamps
- **The Problem with Timestamps:**
  If a pipeline names output files with runtime timestamps (e.g., `chunks_20260911_020000.parquet`, `chunks_20260911_020015.parquet`), every retry creates a new physical file on disk. When a downstream consumer queries `pd.read_parquet('chunks/')`, it concatenates all files, multiplying records by the retry count.
- **The Deterministic Solution:**
  Deterministic naming generates file paths strictly from immutable business keys: `{ticker}_{year}_chunks.parquet`. If Task 3 retries three times, it writes to `NVDA_2026_chunks.parquet` three times. On disk, exactly one file exists, and downstream consumers read consistent, deduplicated data.

#### Atomic Overwrite
- **Definition:** A write strategy where a new version of a dataset completely replaces the old version in an indivisible step, preventing partial writes and eliminating duplicate record accumulation.

---

## 3. Data Preprocessing for Generative AI & RAG

### Interviewer Question
> "At the Gold and Curated tiers, narrative risk factors from Item 1A are split into 500-word sliding windows with a 100-word overlap before vector indexing into ChromaDB.
> 1. Why not feed the entire Form 10-K document directly into Gemini AI instead of chunking and indexing?
> 2. What is the technical justification for the 100-word overlap between chunks?"

### Candidate's Original Response & Core Intuition
- **Core Understanding:** Passing the entire filing to the LLM is impractical, increases latency, and inflates API costs. Embedding text into 384-dimensional vectors enables accurate similarity search. The 100-word overlap preserves context and prevents loss of meaning across chunk boundaries.
- **Evaluation:** Accurate understanding of latency, cost, vector dimensions, and boundary continuity. Needs enhancement with formal AI engineering terminology (Context Window economics, Lost in the Middle degradation, Boundary Truncation).

### Senior Engineering Model Answer
> "We avoid passing full Form 10-K reports directly into an LLM for three architectural reasons:
> 
> First, **Economic and Latency Constraints:** A complete 10-K filing contains 50,000 to 100,000 words. Injecting the entire filing into every user prompt incurs massive token consumption costs and creates response latencies exceeding several seconds.
> 
> Second, the **'Lost in the Middle' Phenomenon:** Research demonstrates that when LLMs process massive context windows, their attention mechanism degrades on facts situated in the middle of long texts. They recall information at the beginning and end of the prompt far better than intermediate paragraphs. Dense vector retrieval isolates the top 5 most semantically relevant paragraphs, keeping prompt context dense and reducing hallucination.
> 
> Third, regarding the **100-word sliding overlap (Context Boundary Preservation):** Arbitrary token or word splitting (e.g., strict 500-word cuts) frequently severs a single legal disclosure or risk thesis across two chunks. The first chunk loses its concluding sentence, and the second chunk loses its premise. The 100-word overlap guarantees that every complete argument or paragraph is fully contained within at least one chunk."

### Deep-Dive Terminology Glossary

#### Context Window & Token Economics
- **Context Window:** The maximum number of tokens (words/sub-words) a Large Language Model can accept and generate within a single inference call.
- **Economic Consideration:** While modern models (such as Gemini) possess large context windows (1M+ tokens), pricing is charged per input token. RAG reduces input prompt size from 100,000 tokens to under 2,500 tokens per query, lowering API operational cost by 95%+.

#### "Lost in the Middle" Effect
- **Definition:** An observed behavioral pattern in Transformer self-attention architectures where models exhibit superior recall for facts located at the extreme start and end of prompt context, but fail to attend to information buried deep in the middle.
- **Mitigation via RAG:** Rather than providing a 100-page document, RAG retrieves only the 5 most relevant 500-word segments and injects them cleanly into the prompt header.

#### Semantic Chunking
- **Definition:** The process of dividing continuous narrative text into discrete, logically self-contained passages designed to optimize embedding model representation.
- **Window Sizing:** Windows that are too small (e.g., 50 words) lack sufficient context to capture complex financial risks. Windows that are too large (e.g., 2,000 words) produce diluted embedding vectors where distinct concepts blur together. A 500-word window maps closely to 1-2 distinct business risk discussions.

#### Context Boundary Preservation (Overlap)
- **Definition:** The inclusion of trailing tokens from chunk $N$ into the beginning of chunk $N+1$.
- **Mechanism:**
  ```text
  Raw Document: [ ... Sentence A. Sentence B. Sentence C. Sentence D. Sentence E. ... ]
  
  Chunk 1:      [ ... Sentence A. Sentence B. Sentence C. ]
                                  |---- 100-word overlap ----|
  Chunk 2:                      [ Sentence B. Sentence C. Sentence D. Sentence E. ... ]
  ```
  If Sentence C contains the primary risk statement, it is preserved in both Chunk 1 and Chunk 2, preventing vector similarity fragmentation.

#### Dense Vector Embeddings
- **Definition:** A numerical representation of text where semantic meaning is mapped to coordinates in a high-dimensional vector space.
- **Model Used:** `sentence-transformers/all-MiniLM-L6-v2` produces a 384-dimensional vector for each chunk.
- **Cosine Similarity:** Measures the cosine of the angle between two vectors:
  $$\text{Cosine Similarity} = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|}$$
  Queries about "supply chain delays" calculate similarity against all 262 chunk vectors, returning passages discussing manufacturing lead times, chip shortages, and foundry dependencies without requiring exact keyword matches.

---

## 4. Key Takeaways for Technical Interviews

1. **Focus on Trade-offs:** Never say a technology is "good" or "fast." Explain what you sacrificed (e.g., *"Snappy sacrifices a small amount of compression ratio to achieve 500 MB/s CPU decompression speed"*).
2. **Anchor in Idempotency:** Any pipeline can succeed on a happy path. Senior engineers care about what happens on failure, retry, and duplicate triggers. Always highlight Deterministic Naming and Atomic Overwrites.
3. **Data Quality First:** Mention Quality Gates before discussing machine learning or LLMs. Clean, verified data is the prerequisite for reliable AI outputs.

---

## 5. Advanced Systems Engineering: Chunk Identity, Index Sequencing, and Orphan Record Management

### Interviewer Question
> "When your pipeline slices documents into chunks, how does the system ensure that indexing consistently restarts from `0001` on every retry rather than skipping ahead to `0002` or `0046`?
> Furthermore, what happens if the source text undergoes slight modifications between runs (e.g., an amended 10-K/A or cleaning fix) causing chunk boundaries to drift or chunk counts to shrink? How do you prevent stale, obsolete vectors from lingering in your Vector Database?"

### Candidate's Original Response & Core Intuition
- **Core Understanding:** Inquired why the numbering starts fresh at `0001` rather than incrementing, and recognized that if raw text changes slightly between two chunking runs, duplicate or divergent records could be created if not properly managed.
- **Evaluation:** Touches upon fundamental distributed state and cache invalidation challenges: Stateless loops vs Stateful sequence generators, and the Orphan Record anomaly in vector stores.

### Senior Engineering Model Answer
> "We address index consistency and data drift through two decoupled architectural principles:
> 
> First, for **Index Consistency (Why retries always restart at `0001`):**
> Index assignment is **stateless**. Rather than relying on a stateful database counter (such as an `AUTO_INCREMENT` sequence or global atomic counter), the chunking pipeline uses a local memory generator:
> ```python
> for idx, text in enumerate(raw_chunks, start=1):
>     chunk_id = f'{ticker}_{year}_RF_{idx:04d}'
> ```
> Every time `chunk_for_rag` executes, the function creates a fresh Python list of slices in ephemeral memory. The `enumerate` pointer always initializes at `1` for the first element. Because the loop maintains zero state across process restarts, the first chunk of Nvidia 2026 is deterministically labeled `NVDA_2026_RF_0001` on every invocation.
> 
> Second, for **Text Drift and the Orphan Record Problem:**
> What happens if an amendment or text cleaning revision alters the document?
> - **Scenario A (Content Modified, Chunk Count Identical):** If the revision retains exactly 45 chunks, an `upsert(id=chunk_id)` directly replaces the old text and dense vector with the new embedding at the identical primary key.
> - **Scenario B (Text Shrinkage / Boundary Shift):** If the document is shortened such that the previous run generated 45 chunks (`0001` to `0045`), but the revised run only yields 40 chunks (`0001` to `0040`), a naive upsert creates **Orphan Records**: chunks `0041` through `0045` from the prior run remain active in the vector collection as ghost data, corrupting search retrieval.
> 
> To permanently eliminate orphan records, we apply the **Partition Purge Pattern**:
> Before indexing the revised chunks of a firm, the pipeline issues a scoped deletion:
> ```python
> collection.delete(where={'$and': [{'ticker': ticker}, {'year': year}]})
> ```
> This purges all pre-existing vectors for that specific `(ticker, year)` partition, ensuring that obsolete trailing chunks are destroyed before new vectors are inserted."

### Deep-Dive Terminology Glossary

#### Stateless Enumeration vs. Stateful Sequence Counters
- **Stateful Counter (`AUTO_INCREMENT` / Sequence):** A shared database state that tracks the highest allocated ID. If Run 1 inserts 45 rows and fails, Run 2 starts allocating IDs at `46`. This breaks deterministic primary key guarantees and produces non-idempotent IDs across retries.
- **Stateless Loop (`enumerate`):** An in-memory iteration over an ordered list where the initial position is fixed at runtime. It guarantees identical ID sequences regardless of how many times the process previously executed.

#### Orphan Records (Ghost Vectors)
- **Definition:** Stale records remaining in a database when an updated source entity produces fewer output units than the previous execution.
- **Impact on Vector Search:** If obsolete chunks are not pruned, dense semantic search will continue to retrieve them, introducing conflicting or invalidated facts into the LLM prompt context and inducing hallucinations.

#### Partition Purge Pattern (Scoped Deletion)
- **Definition:** The practice of clearing all records belonging to a defined logical partition (e.g., firm and fiscal year) immediately before writing the refreshed dataset.
- **Implementation:** `collection.delete(where={'ticker': 'NVDA', 'year': 2026})` followed by `collection.add(...)`. This preserves vectors belonging to other firms (e.g., AAPL, MSFT) while enforcing complete consistency for the active target.

#### Content Hashing (Cryptographic Identity via SHA-256)
- **Advanced Alternative to Sequential IDs:**
  ```python
  import hashlib
  content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
  chunk_id = f'{ticker}_{year}_{content_hash}'
  ```
- **Mechanism:** The chunk ID is derived directly from the cryptographic digest of the text.
- **Benefits:**
  1. If text is unchanged: The hash matches, skipping expensive re-embedding.
  2. If text changes by even a single character: The hash changes completely, providing immediate tamper and drift detection.

---

## 6. Advanced Retrieval Systems: Dense vs. Sparse Search, Lexical Traps, and Reciprocal Rank Fusion (RRF)

### Interviewer Question
> "Why does single-stage Dense Vector Search often perform poorly on financial filings like Form 10-K?
> How does your system combine BM25 and vector embeddings, and why did you choose Reciprocal Rank Fusion (RRF) over simple linear score interpolation?"

### Candidate's Core Intuition
- **Core Understanding:** Dense embeddings map meaning into semantic space, which works well for paraphrasing but fails when seeking exact identifiers (ticker symbols, regulatory statutory codes like EAR99, Item 1A, or specific legal clauses).
- **Hybrid Necessity:** Combining keyword frequency (BM25) with semantic vectors covers both lexical precision and semantic recall.
- **Fusion Challenge:** Cosine similarity (bounded between 0 and 1) cannot be simply added to unbounded BM25 scores (e.g., 0 to 25+) without distortion, making rank-based fusion (RRF) the mathematically robust solution.

### Senior Engineering Model Answer
> "In financial information retrieval, single-stage Dense Semantic Search exhibits two major vulnerabilities:
> 
> 1. **The Lexical Trap & Entity Dilution:** Embedding models compress 500 words into a fixed 384-dimensional vector. Rare domain-specific terms, statutory references (e.g., 'EAR99 export regulations', 'Item 1A'), and numerical accounting codes get diluted across general semantic dimensions. A query for 'TSMC foundry constraints' might retrieve general semiconductor discussions while missing chunks containing the exact supplier name.
> 2. **Out-of-Vocabulary (OOV) & Acronym Sensitivity:** Pure vector search struggles with specialized financial abbreviations or novel corporate legal codifications not adequately represented in general pre-training corpora.
> 
> To resolve this, our pipeline implements **Hybrid Retrieval with Reciprocal Rank Fusion (RRF)**:
> - **Sparse Path (BM25):** Evaluates term frequency and inverse document frequency (TF-IDF variant) across the Gold Parquet chunk corpus, guaranteeing high recall for exact tokens, ticker symbols, and statutory identifiers.
> - **Dense Path (ChromaDB + SentenceTransformers):** Captures conceptual relationships where different words share identical financial semantics (e.g., 'chip shortages' vs 'foundry allocation deficits').
> - **Rank Fusion (RRF):** Instead of attempting to normalize disparate score scales, RRF aggregates candidates based purely on their ordinal positions in each retrieval list:
>   $$\text{RRF}(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
>   where $k = 60$ is a smoothing constant, $M = \{\text{Dense}, \text{BM25}\}$, and $r_m(d)$ is the 1-based rank of document $d$ in system $m$.
> 
> Documents appearing near the top of both systems receive the highest cumulative reciprocal scores. This permanently bypasses the **Score Calibration Problem** without requiring expensive cross-encoder models."

### Deep-Dive Terminology Glossary

#### Okapi BM25 Formulation
- **Inverse Document Frequency (IDF):**
  $$\text{IDF}(q_i) = \ln\left(\frac{N - n(q_i) + 0.5}{n(q_i) + 0.5} + 1.0\right)$$
  Penalizes ubiquitous words across 10-K filings (such as 'company', 'fiscal', 'operations') while exponentially boosting rare terms (such as 'EUV', 'TSMC', 'ASML').
- **Score Calculation:**
  $$\text{Score}(D, Q) = \sum_{i=1}^n \text{IDF}(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$
  Where $k_1 = 1.5$ modulates term frequency saturation and $b = 0.75$ controls document length normalization.

#### The Score Calibration Dilemma
- **Problem:** Dense retrieval produces cosine similarities $\in [0, 1]$, whereas BM25 yields unbounded non-negative scores $[0, \infty)$ dependent on query length and corpus statistics.
- **Failure of Linear Sum:** $Score = \alpha \cdot Score_{\text{dense}} + (1 - \alpha) \cdot Score_{\text{bm25}}$ fails because the distribution variance of BM25 shifts unpredictably across short vs long queries.
- **RRF Solution:** RRF relies strictly on ordinal rank positions ($1, 2, 3, \dots$). The maximum contribution of any single retriever to document $d$ is bounded by $\frac{1}{k + 1} \approx 0.01639$, preventing one retrieval modality from disproportionately dominating the ranking.
