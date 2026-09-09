# SEC Financial Data Pipeline and RAG System

End-to-end financial data engineering pipeline and AI Retrieval-Augmented Generation (RAG) system built on SEC EDGAR Form 10-K annual filings using a 4-tier Medallion Lakehouse Architecture.

---

## Overview

This project implements an automated, production-grade data pipeline that ingests, cleans, transforms, and structures SEC financial reports into semantic chunks ready for vector databases and Large Language Model (LLM) querying.

The pipeline processes financial disclosures from major US technology companies (AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA), strips noisy HTML and XBRL markup, isolates high-value risk factors (Item 1A), and generates enriched semantic chunks stored in Snappy-compressed columnar Parquet format.

---

## Key Features

- Automated SEC EDGAR Ingestion: Fetches metadata for 10,400+ public companies and downloads raw annual Form 10-K filings via official SEC REST APIs.
- Medallion Lakehouse Architecture: Organizes data flow into four quality tiers: Bronze (Raw), Silver (Cleaned and Structured), Gold (Semantic Chunks), and Curated (Vector Store).
- Storage Optimization: Converts raw SEC JSON disclosures into columnar Snappy Parquet, achieving over 75% disk storage savings.
- HTML and XBRL Extraction: Traverses document DOM structures to eliminate scripts, inline styling, and metadata headers, extracting Item 1A (Risk Factors) sections into clean Markdown.
- Semantic Chunking: Segments financial narratives into sliding-window chunks (500 words, 100-word overlap) tagged with structured metadata (chunk ID, ticker, fiscal year, section, word count).
- Automated Testing and Verification: End-to-end test suite enforcing data schema contracts, non-empty text fields, and CIK standard compliance across all companies.

---

## System Architecture

```text
[SEC EDGAR REST API]
         |
         | (Step 1, 3: Ingestion)
         v
+-------------------------------------------------------------+
| BRONZE LAYER (data/01_raw/)                                 |
| - companies/all_companies.json                              |
| - sec_filings/{TICKER}/*.htm (Raw Form 10-K HTML files)     |
+-------------------------------------------------------------+
         |
         | (Step 2, 4: Cleaning and Normalization)
         v
+-------------------------------------------------------------+
| SILVER LAYER (data/02_staging/)                             |
| - companies_clean.parquet (10-digit zero-padded CIK)        |
| - sec_filings/{TICKER}/*_risk_factors.md                    |
+-------------------------------------------------------------+
         |
         | (Step 5: Semantic Chunking and Metadata Enrichment)|
         v
+-------------------------------------------------------------+
| GOLD LAYER (data/03_primary/)                               |
| - chunks/{TICKER}_{YEAR}_chunks.parquet                     |
| - chunks/all_chunks.parquet (Consolidated 262 chunks)       |
+-------------------------------------------------------------+
         |
         | (Step 6: Embedding and Indexing)
         v
+-------------------------------------------------------------+
| CURATED LAYER (data/04_curated/)                            |
| - vector_db/ (Vector Store: Qdrant / Chroma / FAISS)        |
+-------------------------------------------------------------+
```

---

## Directory Structure

```text
.
|-- .agents/
|   `-- rules/
|       `-- no-decorative-symbols.md
|-- AGENTS.md
|-- README.md
|-- pyproject.toml
|-- requirements.txt
|-- run.py
|-- config/
|   `-- base_config.yaml
|-- data/
|   |-- 01_raw/
|   |   |-- companies/
|   |   `-- sec_filings/
|   |-- 02_staging/
|   |   |-- companies_clean.parquet
|   |   `-- sec_filings/
|   |-- 03_primary/
|   |   `-- chunks/
|   `-- 04_curated/
|       `-- vector_db/
|-- docs/
|   |-- architecture.md
|   `-- project_learning_journal.md
|-- infra/
|   `-- docker-compose.yml
|-- notebooks/
|   `-- 01_pipeline_demo.ipynb
|-- src/
|   |-- common/
|   |   |-- config.py
|   |   `-- logger.py
|   |-- ingestion/
|   |   |-- extract_companies.py
|   |   `-- ingest_10k_filings.py
|   |-- rag/
|   |   `-- chunking.py
|   `-- transformation/
|       |-- clean_10k_to_text.py
|       `-- clean_companies.py
`-- tests/
    `-- test_pipeline.py
```

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Accnoname/sec-financial-data-pipeline.git
   cd sec-financial-data-pipeline
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Pipeline Execution

The master pipeline orchestrator is located in `run.py`. It provides CLI commands to execute individual steps or run the entire workflow end-to-end.

### Run All Pipeline Steps

```bash
python run.py all
```

### Run Individual Steps

```bash
# Step 1: Fetch company directory from SEC EDGAR (Bronze)
python run.py 1

# Step 2: Normalize CIK codes and export to Parquet (Silver)
python run.py 2

# Step 3: Ingest Form 10-K filings for target companies (Bronze)
python run.py 3

# Step 4: Extract Item 1A Risk Factors to Markdown for all companies (Silver)
python run.py 4

# Step 4 for a single company:
python run.py 4 AAPL

# Step 5: Perform semantic chunking and generate Gold Parquet datasets
python run.py 5

# Step 5 for a single company:
python run.py 5 NVDA
```

---

## Automated Testing

Run the automated test suite with pytest to validate data schemas, extraction integrity, and file generation across all stages:

```bash
python -m pytest tests/ -v
```

### Test Coverage

- `test_raw_companies_json_exists`: Verifies raw SEC company data exists and meets size thresholds.
- `test_raw_sec_filings_exist`: Ensures all target companies have downloaded Form 10-K HTML files exceeding 500 KB.
- `test_staging_parquet_schema`: Validates 10-digit zero-padded CIK string formatting and required schema columns.
- `test_markdown_risk_factors_all_tickers`: Confirms successful extraction of Item 1A text (>10,000 characters) across all companies.
- `test_gold_chunks_schema_and_content`: Checks chunk count, metadata columns, and non-empty text records in `all_chunks.parquet`.

---

## Data Specifications

| Layer | Path | Format | Description |
| :--- | :--- | :--- | :--- |
| Bronze | `data/01_raw/companies/` | JSON | Raw company tickers and exchange mapping (10,400+ records) |
| Bronze | `data/01_raw/sec_filings/` | HTML | Raw annual Form 10-K filings from SEC EDGAR |
| Silver | `data/02_staging/companies_clean.parquet` | Parquet (Snappy) | Cleaned company master list with standardized 10-digit CIKs |
| Silver | `data/02_staging/sec_filings/{TICKER}/` | Markdown | Extracted and normalized Item 1A Risk Factors text |
| Gold | `data/03_primary/chunks/` | Parquet / JSON | 500-word sliding-window chunks with metadata IDs and word counts |
| Curated | `data/04_curated/vector_db/` | Vector Store | Indexed vector embeddings for semantic search and RAG QA |

---

## Technology Stack

- Language: Python 3.10+
- Data Processing: Pandas, PyArrow (Snappy compression)
- Parsing and Extraction: BeautifulSoup4, lxml, RegEx
- Ingestion and Networking: Requests
- Infrastructure: Docker Compose (PostgreSQL, Qdrant Vector Store, MinIO)
- Testing: Pytest

---

## License

This project is licensed under the MIT License.
