# SEC Financial Data Pipeline and AI RAG System

Enterprise-Grade Financial Data Pipeline and Retrieval-Augmented Generation (RAG) Platform built on SEC EDGAR Form 10-K Filings using a 4-Tier Medallion Lakehouse Architecture.

---

## Executive Overview

This repository implements an automated, production-grade data engineering pipeline and AI question-answering system. The platform ingests, validates, standardizes, and indexes annual financial disclosures (Form 10-K) from major US technology corporations: Apple (AAPL), Amazon (AMZN), Alphabet (GOOGL), Meta (META), Microsoft (MSFT), Nvidia (NVDA), and Tesla (TSLA).

Moving beyond static web-scraping scripts, this system applies resilient data engineering patterns:
- **Change Data Detection (Sensor Pattern):** Polls SEC EDGAR submissions metadata to detect new annual filings by accession number, completing daily checks in approximately 3 seconds and short-circuiting downstream tasks when data is current.
- **Resilient DAG Orchestrator:** Implements an in-house Directed Acyclic Graph (DAG) task engine featuring topological execution, automated retry with exponential backoff and jitter, and pre/post-execution quality validation gates.
- **Medallion Lakehouse Architecture:** Enforces progressive data refinement across Bronze, Silver, Gold, and Curated storage tiers, compressing raw disclosures into Snappy-encoded columnar Parquet.
- **Context-Grounded Financial AI (RAG):** Segments business risk factors (Item 1A) into overlapping semantic chunks, indexes them into a local ChromaDB vector store, and synthesizes answers via Gemini AI with strict source citations linking back to original SEC documents.
- **Automated Daemon Scheduling:** Native Windows Task Scheduler integration (`setup_windows_task.bat`) to run automated ingestion silently at 02:00 AM daily without manual terminal interaction.

---

## Architecture Diagram

```text
+---------------------------------------------------------------------------------------+
|                                    DATA SOURCES                                       |
|  SEC EDGAR REST Submissions API (https://data.sec.gov/submissions/CIK{cik}.json)      |
|  SEC EDGAR Archives (Raw 10-K HTML / XBRL Annual Reports)                             |
+-------------------------------------------+-------------------------------------------+
                                            |
                                            | 1. Metadata Sensor & Check (Accession Match)
                                            v
+---------------------------------------------------------------------------------------+
|                               ORCHESTRATION ENGINE (DAG)                             |
|  - Topological Task Ordering       - Quality Gates (Schema, Size, Null Checks)       |
|  - Exponential Backoff with Jitter - JSONL Structured Audit Logger                    |
+-------------------------------------------+-------------------------------------------+
                                            |
                   +------------------------+------------------------+
                   |                                                 |
                   v (If New Filing Detected)                        v (If Data Up-to-Date)
+--------------------------------------+     +------------------------------------------+
| 01_RAW (BRONZE LAYER)                |     | SHORT-CIRCUIT AUDIT                      |
| - companies/all_companies.json       |     | - Status: SKIPPED (Cache Valid)          |
| - sec_filings/{TICKER}/*.htm (Raw)   |     | - Execution Duration: < 4 seconds        |
| - sec_filings/{TICKER}/metadata.json |     | - Zero redundant API/compute expenditure |
+------------------+-------------------+     +------------------------------------------+
                   |
                   | 2. Parsing, DOM Stripping, CIK Normalization
                   v
+---------------------------------------------------------------------------------------+
| 02_STAGING (SILVER LAYER)                                                             |
| - companies_clean.parquet (Standardized 10-digit CIK, deduplicated, Snappy compressed)|
| - sec_filings/{TICKER}/*_risk_factors.md (Extracted Item 1A Business Risk Narratives)  |
+------------------+--------------------------------------------------------------------+
                   |
                   | 3. Semantic Chunking (500 words, 100-word sliding overlap)
                   v
+---------------------------------------------------------------------------------------+
| 03_PRIMARY (GOLD LAYER)                                                               |
| - chunks/{TICKER}_{YEAR}_chunks.parquet (Analytical chunk dataset)                    |
| - chunks/all_chunks.parquet (Consolidated 262 semantic units with word counts)        |
+------------------+--------------------------------------------------------------------+
                   |
                   | 4. Vector Embedding (SentenceTransformers: all-MiniLM-L6-v2)
                   v
+---------------------------------------------------------------------------------------+
| 04_CURATED (SERVING LAYER)                                                            |
| - vector_db/ (ChromaDB Persistent Vector Store, Cosine Similarity Index)              |
+------------------+--------------------------------------------------------------------+
                   |
                   | 5. Top-K Semantic Retrieval & LLM Grounding (Gemini AI)
                   v
+---------------------------------------------------------------------------------------+
| AI RAG QUERY INTERFACE                                                                |
| - Output: Synthesized Risk Analysis + Full Citation Trail & SEC Document Audit Links  |
+---------------------------------------------------------------------------------------+
```

---

## Core Engineering Capabilities

### 1. SEC Filing Sensor & Delta Detection
Financial disclosures for a given firm are typically filed once per fiscal year. Re-downloading, parsing, and embedding massive reports continuously constitutes an anti-pattern.
- The pipeline queries `https://data.sec.gov/submissions/CIK{padded_cik}.json` and extracts the latest `accessionNumber` and `filingDate`.
- Compares the remote metadata against local state in `data/01_raw/sec_filings/{ticker}/metadata.json`.
- If the accession number matches and local artifacts exist, ingestion is skipped.
- The DAG captures this signal (`has_changes: false`) and automatically bypasses downstream transformation and embedding tasks, logging a clean audit record in ~3 seconds.

### 2. DAG Orchestrator with Quality Gates and Self-Healing
- **Dependency Tracking:** Resolves dependencies between pipeline steps and prevents downstream execution if an upstream dependency fails.
- **Exponential Backoff Retry:** Network requests and API endpoints are guarded by configurable retries with exponential backoff and randomized jitter to mitigate rate-limiting.
- **Quality Gates:** Pre- and post-execution assertions validate file presence, minimum byte size, Parquet schema columns, and minimum record counts before passing data to subsequent stages.
- **Audit Logging:** Every DAG execution appends structured JSONL telemetry to `logs/orchestration_audit.jsonl` detailing duration in milliseconds, retry counts, and status.

### 3. Medallion Storage and Format Optimization
- Converts uncompressed JSON and HTML documents into columnar Snappy Parquet.
- Enforces strict data contracts: 10-digit zero-padded CIK strings, upper-cased ticker symbols, and boolean tier indicators.
- Columnar format allows analytical engines to scan single attributes (e.g., `ticker`, `word_count`) via column projection and dictionary encoding, significantly reducing I/O footprint.

### 4. Financial AI RAG with Full Citation Trail
- Extracts narrative risk disclosures from Item 1A, stripping boilerplate SEC headers, page counters, and XBRL markup.
- Segments text into 500-word sliding windows with 100-word overlap to preserve semantic continuity across paragraph boundaries.
- Employs SentenceTransformers (`all-MiniLM-L6-v2`) to produce 384-dimensional dense vectors stored in ChromaDB.
- When queried, retrieves the top 5 semantically relevant chunks and passes them to Gemini AI with strict citation instructions, outputting grounded answers accompanied by references to exact Markdown and raw HTML source files.

---

## Data Tier Specifications

| Layer | Storage Path | Format | Schema & Description |
| :--- | :--- | :--- | :--- |
| **Bronze** | `data/01_raw/companies/` | JSON | Raw company directory from SEC EDGAR (10,400+ public entities). |
| **Bronze** | `data/01_raw/sec_filings/{TICKER}/` | HTML / JSON | Raw Form 10-K disclosures (1-8 MB each) and filing metadata state. |
| **Silver** | `data/02_staging/companies_clean.parquet` | Parquet (Snappy) | Normalized schema: `cik` (String), `ticker` (String), `name` (String), `exchange` (String), `is_major` (Boolean). |
| **Silver** | `data/02_staging/sec_filings/{TICKER}/` | Markdown | Extracted and normalized Item 1A Risk Factors text. |
| **Gold** | `data/03_primary/chunks/` | Parquet / JSON | Schema: `chunk_id` (String), `ticker` (String), `year` (Int64), `section` (String), `chunk_index` (Int64), `text` (String), `word_count` (Int64). Total: 262 chunks. |
| **Curated**| `data/04_curated/vector_db/` | ChromaDB / Vector | Persistent cosine vector collection (`sec_risk_factors`). |

---

## Repository Structure

```text
sec-financial-data-pipeline/
|-- .env                                # Environment configurations (API keys, models)
|-- AGENTS.md                           # Engineering standards and behavioral rules
|-- README.md                           # System architecture and documentation
|-- pyproject.toml                      # Project metadata and pytest configuration
|-- requirements.txt                    # Project Python dependencies
|-- run.py                              # Master CLI and execution orchestrator
|-- setup_windows_task.bat              # Windows Task Scheduler registration script
|-- data/                               # Medallion Lakehouse storage (local data lake)
|   |-- 01_raw/                         # Bronze Layer: Raw SEC JSON and 10-K HTML
|   |-- 02_staging/                     # Silver Layer: Normalized Parquet and Markdown
|   |-- 03_primary/                     # Gold Layer: Consolidated semantic chunks
|   `-- 04_curated/                     # Curated Layer: ChromaDB vector collections
|-- docs/                               # Architectural blueprints and engineering guides
|   |-- architecture.md
|   `-- system_architecture_and_design_guide.md
|-- logs/                               # Structured audit and scheduler run logs
|   `-- orchestration_audit.jsonl
|-- src/                                # Modular pipeline source code
|   |-- common/                         # Shared utilities, configs, and loggers
|   |   |-- config.py
|   |   `-- logger.py
|   |-- ingestion/                      # Bronze data acquisition modules
|   |   |-- extract_companies.py        # SEC company master list ingestion
|   |   `-- ingest_10k_filings.py       # 10-K retrieval with Delta Change Detection
|   |-- orchestration/                  # Enterprise pipeline orchestration engine
|   |   |-- dag.py                      # PipelineDAG dependency coordinator
|   |   |-- quality_gate.py             # Pre/post execution quality assertions
|   |   |-- scheduler.py                # Standalone daemon scheduling loop
|   |   |-- state.py                    # Task status models and execution telemetry
|   |   `-- task.py                     # Resilient task runner with backoff retry
|   |-- rag/                            # Retrieval-Augmented Generation subsystem
|   |   |-- chunking.py                 # Semantic chunking and metadata tagger
|   |   |-- embedder.py                 # Vector embedding indexer (ChromaDB)
|   |   `-- retriever.py                # Top-K retrieval and Gemini LLM synthesis
|   `-- transformation/                 # Silver cleaning and extraction modules
|       |-- clean_10k_to_text.py        # Item 1A Risk Factors regex/HTML parser
|       `-- clean_companies.py          # CIK 10-digit zero-padding and normalization
`-- tests/                              # Automated test suite
    |-- test_pipeline.py                # End-to-end integration tests
    `-- unit/                           # Module unit tests
        |-- test_orchestration.py       # DAG, retry, and quality gate tests
        `-- test_units.py               # Parsing, chunking, and validation tests
```

---

## Quickstart & Execution Guide

### Prerequisites

- Python 3.10 or higher
- Git
- Valid Gemini API key (placed in `.env` as `GEMINI_API_KEY=...`)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Accnoname/sec-financial-data-pipeline.git
   cd sec-financial-data-pipeline
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. Install production and development dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables in `.env`:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   EMBEDDING_MODEL=all-MiniLM-L6-v2
   GEMINI_MODEL=gemini-2.5-flash
   ```

---

### Command Line Interface (`run.py`)

The pipeline CLI provides convenient entry points for automated workflows and individual tasks:

```bash
# Display CLI usage manual
python run.py

# Run standard incremental DAG with Delta Sensor (Recommended)
python run.py dag

# Force full re-download and re-indexing from scratch
python run.py dag --force

# Query the Financial AI Assistant (RAG)
python run.py 7 "What are the primary supply chain and antitrust risks facing Nvidia?"

# Smart question invocation (automatically routes text to RAG query engine)
python run.py "How does Apple assess geopolitical and foreign exchange risks?"

# Execute individual stages manually:
python run.py 1           # Step 1: Ingest SEC company master directory
python run.py 2           # Step 2: Normalize CIKs to Silver Parquet
python run.py 3           # Step 3: Run SEC filing sensor and 10-K download
python run.py 4           # Step 4: Extract Item 1A Markdown for all firms
python run.py 4 MSFT      # Step 4: Extract Item 1A for Microsoft only
python run.py 5           # Step 5: Perform semantic chunking into Gold Parquet
python run.py 6           # Step 6: Generate embeddings and build ChromaDB index
```

---

## Automated Scheduling on Windows

To run the pipeline hands-free on a Windows machine:

1. Right-click [setup_windows_task.bat](file:///d:/H%E1%BB%87%20Th%E1%BB%91ng/setup_windows_task.bat) and select **Run as administrator**.
2. The script configures Windows Task Scheduler to execute `python run.py dag` silently via `pythonw.exe` every day at **02:00 AM**.
3. **Behavior:**
   - On days where no new 10-K filings have been submitted to SEC EDGAR, the task executes in ~3 seconds and terminates with zero CPU or API token overhead.
   - When a company files a new annual disclosure, the task downloads the report, extracts risk factors, generates semantic chunks, updates ChromaDB, and logs the event to `logs/orchestration_audit.jsonl`.

---

## Testing and Verification

The test suite validates data contracts, schema compliance, extraction thresholds, and DAG orchestration resilience:

```bash
python -m pytest tests -v
```

### Test Suite Summary (18 Tests, 100% Pass)
- `tests/test_pipeline.py`: Validates file presence across Bronze, Silver, and Gold tiers; verifies CIK formatting, Parquet column structures, and chunk row counts (>200).
- `tests/unit/test_orchestration.py`: Validates topological DAG execution order, automated retry triggers under simulated network failure, and QualityGate assertion failures.
- `tests/unit/test_units.py`: Tests unit functionality of CIK zero-padding, Item 1A regex isolation, and sliding-window boundary calculations.

---

## Author & Engineering Profile

**Project Author:** [Nguyen Van A / Accnoname]  
**Specialization:** Data Engineering, Distributed Data Systems, Data Modeling, Lakehouse Architecture  
**Portfolio Repository:** [https://github.com/Accnoname/sec-financial-data-pipeline](https://github.com/Accnoname/sec-financial-data-pipeline)  
**LinkedIn:** [https://linkedin.com/in/your-profile](https://linkedin.com/in/your-profile)  
**Contact Email:** [contact.engineer@example.com](mailto:contact.engineer@example.com)

### Technical Competencies Demonstrated in this Project:
- **Data Engineering Principles:** Idempotency, Change Data Capture (CDC), High-Water Mark tracking, Medallion Architecture, Columnar Data Storage (Parquet, Snappy).
- **Orchestration & Workflow Design:** Custom DAG engines, Task Lifecycles, Exponential Backoff with Jitter, Pre/Post Quality Gates, Audit Telemetry.
- **Data Quality & Governance:** Strict Schema Enforcement, Quality Gate assertions, Null handling, CIK Standard Validation.
- **AI & Retrieval-Augmented Generation:** Semantic Vector Embedding, Dense Retrieval (ChromaDB), Grounded Prompt Engineering with Source Audit Trail.
- **Production Mindset:** Modular Python OOP architecture, 100% test coverage with Pytest, automated daily execution via native OS scheduler.

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.
