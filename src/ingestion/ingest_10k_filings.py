import time
from pathlib import Path
import pandas as pd
import requests

from src.common.config import RAW_DIR, STAGING_DIR
from src.common.logger import get_logger

logger = get_logger("ingest_10k_filings")
SEC_HEADERS = {"User-Agent": "StockMarketRAGProject student@university.edu.vn"}
TARGET_TICKERS = ["GOOGL", "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA"]


def get_10k_url(cik: str) -> tuple[str, str] | None:
    """Trả về (filename, url) của bản 10-K mới nhất"""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        filings = resp.json().get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        accessions = filings.get("accessionNumber", [])
        docs = filings.get("primaryDocument", [])

        for i, form in enumerate(forms):
            if form == "10-K":
                acc = accessions[i].replace("-", "")
                doc = docs[i]
                return doc, f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}"
    except Exception as e:
        logger.error(f"Lỗi tra cứu CIK {cik}: {e}")
    return None


def ingest_filings() -> list[Path]:
    parquet_path = STAGING_DIR / "companies_clean.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"Chưa có file {parquet_path}. Hãy chạy Bước 2 trước.")

    df = pd.read_parquet(parquet_path)
    targets = df[df["ticker"].isin(TARGET_TICKERS)]
    saved = []

    for _, row in targets.iterrows():
        ticker, cik = row["ticker"], row["cik"]
        ticker_dir = RAW_DIR / "sec_filings" / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)

        existing = list(ticker_dir.glob("*.htm*"))
        if existing:
            logger.info(f"[{ticker}] Đã có sẵn: {existing[0].name}")
            saved.append(existing[0])
            continue

        result = get_10k_url(cik)
        if not result:
            continue
        doc_name, doc_url = result

        logger.info(f"[{ticker}] Đang tải {doc_name}...")
        time.sleep(0.2)
        resp = requests.get(doc_url, headers=SEC_HEADERS, timeout=30)
        resp.raise_for_status()

        out_file = ticker_dir / doc_name
        out_file.write_text(resp.text, encoding="utf-8", errors="ignore")
        saved.append(out_file)
        logger.info(f"[{ticker}] Đã lưu {out_file.name}")

    return saved


if __name__ == "__main__":
    ingest_filings()

