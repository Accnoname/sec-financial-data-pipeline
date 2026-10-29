"""Backward-compatibility forwarder for src.bronze.ingest_10k_filings."""
from src.bronze.ingest_10k_filings import *
from src.bronze.ingest_10k_filings import ingest_filings, get_latest_10k_metadata

if __name__ == "__main__":
    ingest_filings()
