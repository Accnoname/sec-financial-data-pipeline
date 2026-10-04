import json
import sys
import time
from pathlib import Path
from typing import Any
import pandas as pd
import requests

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.common.config import RAW_DIR, STAGING_DIR
from src.common.logger import get_logger

logger = get_logger("ingest_10k_filings")
SEC_HEADERS = {"User-Agent": "StockMarketRAGProject student@university.edu.vn"}
TARGET_TICKERS = ["GOOGL", "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA"]


def get_latest_10k_metadata(cik: str) -> dict[str, Any] | None:
    """Tra cuu metadata cua ban 10-K moi nhat tu SEC EDGAR submissions API."""
    padded_cik = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{padded_cik}.json"
    try:
        resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        accessions = filings.get("accessionNumber", [])
        filing_dates = filings.get("filingDate", [])
        docs = filings.get("primaryDocument", [])
        company_name = data.get("name", "")

        for i, form in enumerate(forms):
            if form == "10-K":
                acc_raw = accessions[i]
                acc_clean = acc_raw.replace("-", "")
                doc = docs[i]
                filing_date = filing_dates[i] if i < len(filing_dates) else ""
                download_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{doc}"
                return {
                    "filing_date": filing_date,
                    "accession": acc_raw,
                    "document": doc,
                    "url": download_url,
                    "company_name": company_name,
                }
    except Exception as e:
        logger.error(f"Loi tra cuu metadata SEC cho CIK {cik}: {e}")
    return None


def ingest_filings(force: bool = False) -> dict[str, Any]:
    """
    Kiem tra va tai ve bao cao 10-K moi nhat cho danh muc target tickers.
    Su dung co che Delta Detection de khong tai lai cac bao cao da cap nhat.
    """
    parquet_path = STAGING_DIR / "companies_clean.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"Chua co file {parquet_path}. Hay chay Buoc 2 truoc.")

    df = pd.read_parquet(parquet_path)
    targets = df[df["ticker"].isin(TARGET_TICKERS)]

    existing_files: list[Path] = []
    new_files: list[Path] = []
    new_tickers: list[str] = []

    for _, row in targets.iterrows():
        ticker, cik = row["ticker"], row["cik"]
        ticker_dir = RAW_DIR / "sec_filings" / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        meta_file = ticker_dir / "metadata.json"

        # 1. Tra cuu metadata moi nhat tu SEC
        latest_meta = get_latest_10k_metadata(cik)

        # 2. Neu khong the ket noi SEC API, fallback vao file hien co
        if not latest_meta:
            existing = list(ticker_dir.glob("*.htm*"))
            if existing:
                logger.warning(f"[{ticker}] Khong the ket noi SEC API, dung lai file san co: {existing[0].name}")
                existing_files.append(existing[0])
            continue

        doc_name = latest_meta["document"]
        doc_file = ticker_dir / doc_name
        doc_url = latest_meta["url"]

        # 3. Kiem tra xem ban 10-K nay da co va dung accession number hay chua
        is_already_up_to_date = False
        if not force and meta_file.exists() and doc_file.exists():
            try:
                current_meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if current_meta.get("accession") == latest_meta["accession"]:
                    is_already_up_to_date = True
            except Exception:
                is_already_up_to_date = False

        if is_already_up_to_date:
            logger.info(
                f"[{ticker}] Da cap nhat ban moi nhat tren SEC (Accession: {latest_meta['accession']}, "
                f"Filing Date: {latest_meta['filing_date']}). Bo qua."
            )
            existing_files.append(doc_file)
            continue

        # 4. Phat hien ban 10-K moi hoac force=True
        logger.info(
            f"[{ticker}] Phat hien ban 10-K moi! (Accession: {latest_meta['accession']}, "
            f"Ngay nop: {latest_meta['filing_date']}). Dang tai {doc_name}..."
        )
        time.sleep(0.2)
        resp = requests.get(doc_url, headers=SEC_HEADERS, timeout=30)
        resp.raise_for_status()

        doc_file.write_text(resp.text, encoding="utf-8", errors="ignore")
        meta_file.write_text(
            json.dumps(latest_meta, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        new_files.append(doc_file)
        new_tickers.append(ticker)
        logger.info(f"[{ticker}] Da luu thanh cong {doc_file.name}")

    summary = {
        "total_targets": len(targets),
        "existing_count": len(existing_files),
        "new_downloads_count": len(new_files),
        "new_tickers": new_tickers,
        "has_changes": len(new_files) > 0 or force,
        "saved_paths": [str(p) for p in (new_files + existing_files)],
    }
    logger.info(
        f"Hoan tat Ingestion: {summary['new_downloads_count']} moi, "
        f"{summary['existing_count']} da co san. has_changes={summary['has_changes']}"
    )
    return summary


if __name__ == "__main__":
    ingest_filings()

