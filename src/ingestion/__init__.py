"""Backward-compatibility forwarder for src.bronze."""
from src.bronze import fetch_and_save_companies, ingest_filings, get_latest_10k_metadata

__all__ = ["fetch_and_save_companies", "ingest_filings", "get_latest_10k_metadata"]
