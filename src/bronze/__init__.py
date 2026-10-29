"""
Tầng Bronze (Raw Layer) trong Kiến trúc Medallion Lakehouse.
Bao gồm các pipeline thu thập và lưu trữ dữ liệu thô nguyên vẹn từ SEC EDGAR.
"""

from src.bronze.extract_companies import fetch_and_save_companies
from src.bronze.ingest_10k_filings import ingest_filings, get_latest_10k_metadata

__all__ = ["fetch_and_save_companies", "ingest_filings", "get_latest_10k_metadata"]
