"""
BƯỚC 2: CHUẨN HÓA DỮ LIỆU CÔNG TY SANG PARQUET (SILVER LAYER)
=============================================================
1. Đọc dữ liệu thô all_companies.json từ data/01_raw/companies/
2. Chuẩn hóa CIK về 10 chữ số (chuẩn SEC).
3. Chuẩn hóa Ticker viết hoa, khử trùng lặp.
4. Gán nhãn is_major cho các công ty lớn.
5. Xuất ra data/02_staging/companies_clean.parquet nén Snappy.
"""

from pathlib import Path
import pandas as pd

from src.common.config import RAW_DIR, STAGING_DIR
from src.common.logger import get_logger

logger = get_logger("clean_companies")
MAJOR_TICKERS = {"AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"}


def clean_companies() -> Path:
    raw_file = RAW_DIR / "companies" / "all_companies.json"
    if not raw_file.exists():
        raise FileNotFoundError(f"Thiếu file dữ liệu thô: {raw_file}")

    logger.info(f"Đọc dữ liệu thô: {raw_file}")
    df = pd.read_json(raw_file).dropna(subset=["cik", "ticker", "name"])

    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["name"] = df["name"].astype(str).str.strip()
    df["exchange"] = df["exchange"].astype(str).str.strip()
    df["cik"] = df["cik"].astype(str).str.split(".").str[0].str.zfill(10)
    df = df.drop_duplicates(subset=["ticker"], keep="first")
    df["is_major"] = df["ticker"].isin(MAJOR_TICKERS)

    out_file = STAGING_DIR / "companies_clean.parquet"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_file, index=False, engine="pyarrow", compression="snappy")

    logger.info(f"Đã chuẩn hóa {len(df):,} công ty sang Parquet: {out_file}")
    return out_file


if __name__ == "__main__":
    clean_companies()
