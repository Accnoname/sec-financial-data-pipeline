"""
KIỂM THỬ TOÀN DIỆN PIPELINE (UNIT & INTEGRATION TESTS)
======================================================
Chạy kiểm thử: python -m pytest tests/ -v
"""

from pathlib import Path
import pytest
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MAJOR_TICKERS = ["AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"]


def test_raw_companies_json_exists():
    """Kiểm tra file dữ liệu thô Bronze (all_companies.json) tồn tại và hợp lệ"""
    raw_file = DATA_DIR / "01_raw" / "companies" / "all_companies.json"
    assert raw_file.exists(), f"Không tìm thấy file: {raw_file}"
    assert raw_file.stat().st_size > 100_000, "File JSON quá nhỏ hoặc bị rỗng"


def test_raw_sec_filings_exist():
    """Kiểm tra file HTML Form 10-K gốc của cả 7 tập đoàn lớn"""
    filings_dir = DATA_DIR / "01_raw" / "sec_filings"
    assert filings_dir.exists(), f"Không tìm thấy thư mục: {filings_dir}"

    for ticker in MAJOR_TICKERS:
        ticker_dir = filings_dir / ticker
        assert ticker_dir.exists(), f"Chưa có thư mục raw cho {ticker}"
        htm_files = list(ticker_dir.glob("*.htm*"))
        assert len(htm_files) > 0, f"Thiếu file HTML 10-K cho {ticker}"
        assert htm_files[0].stat().st_size > 500_000, f"File HTML của {ticker} quá nhỏ"


def test_staging_parquet_schema():
    """Kiểm tra file Parquet Silver đã được chuẩn hóa đúng chuẩn CIK 10 chữ số"""
    parquet_file = DATA_DIR / "02_staging" / "companies_clean.parquet"
    assert parquet_file.exists(), f"Không tìm thấy file: {parquet_file}"

    df = pd.read_parquet(parquet_file)
    assert not df.empty, "DataFrame Parquet không được rỗng"

    expected_cols = {"cik", "ticker", "name", "exchange", "is_major"}
    assert expected_cols.issubset(df.columns), f"Thiếu cột trong Parquet: {expected_cols - set(df.columns)}"

    sample_ciks = df["cik"].head(50)
    for cik in sample_ciks:
        assert len(str(cik)) == 10, f"CIK không đúng 10 số: {cik}"
        assert str(cik).isdigit(), f"CIK phải là ký số: {cik}"


def test_markdown_risk_factors_all_tickers():
    """Kiểm tra file Markdown trích xuất phần Item 1A Risk Factors cho cả 7 tập đoàn"""
    staging_dir = DATA_DIR / "02_staging" / "sec_filings"
    assert staging_dir.exists(), f"Không tìm thấy thư mục: {staging_dir}"

    for ticker in MAJOR_TICKERS:
        ticker_dir = staging_dir / ticker
        assert ticker_dir.exists(), f"Chưa có thư mục Silver cho {ticker}"
        md_files = list(ticker_dir.glob("*_risk_factors.md"))
        assert len(md_files) > 0, f"Thiếu file Markdown Risk Factors cho {ticker}"

        content = md_files[0].read_text(encoding="utf-8")
        assert "Risk Factors" in content or "RISK FACTORS" in content, f"Nội dung {ticker} không chứa Risk Factors"
        assert len(content) > 10_000, f"Nội dung Markdown của {ticker} quá ngắn ({len(content)} chars)"


def test_gold_chunks_schema_and_content():
    """Kiểm tra tính toàn vẹn của Tầng Gold (all_chunks.parquet và các file chunks con)"""
    chunks_dir = DATA_DIR / "03_primary" / "chunks"
    unified_parquet = chunks_dir / "all_chunks.parquet"
    assert unified_parquet.exists(), f"Không tìm thấy file tổng hợp: {unified_parquet}"

    df = pd.read_parquet(unified_parquet)
    assert len(df) > 100, f"Số lượng chunks quá ít ({len(df)} chunks)"

    expected_cols = {
        "chunk_id",
        "ticker",
        "year",
        "section",
        "chunk_index",
        "total_chunks",
        "word_count",
        "text",
    }
    assert expected_cols.issubset(df.columns), f"Thiếu cột trong Gold Parquet: {expected_cols - set(df.columns)}"

    # Kiểm tra đủ cả 7 công ty
    tickers_in_chunks = set(df["ticker"].unique())
    assert set(MAJOR_TICKERS).issubset(tickers_in_chunks), f"Thiếu công ty trong chunks: {set(MAJOR_TICKERS) - tickers_in_chunks}"

    # Kiểm tra không có chunk nào rỗng hoặc từ quá ít
    assert df["text"].str.strip().ne("").all(), "Tồn tại chunk có text rỗng"
    assert (df["word_count"] > 0).all(), "Tồn tại chunk có word_count <= 0"
