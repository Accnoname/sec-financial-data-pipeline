import json
from pathlib import Path
import requests

from src.common.config import BRONZE_DIR, RAW_DIR
from src.common.logger import get_logger

logger = get_logger("bronze_extract_companies")
SEC_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
HEADERS = {"User-Agent": "StockMarketRAGDataEngineer student@university.edu.vn"}


def fetch_and_save_companies(force: bool = False) -> Path:
    """Thu thập danh mục công ty từ SEC EDGAR và lưu vào Tầng Bronze."""
    target_dir = BRONZE_DIR if BRONZE_DIR.exists() else RAW_DIR
    out_file = target_dir / "companies" / "all_companies.json"
    if not force and out_file.exists() and out_file.stat().st_size > 100_000:
        logger.info(f"Danh sach cong ty da co san tai Tầng Bronze ({out_file.name}). Bo qua tai lai.")
        return out_file

    logger.info(f"Đang tải danh sách công ty từ SEC.gov: {SEC_URL}")
    resp = requests.get(SEC_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    payload = resp.json()
    fields, rows = payload["fields"], payload["data"]
    companies = [dict(zip(fields, row)) for row in rows]

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(companies, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"Đã lưu {len(companies):,} công ty vào Tầng Bronze: {out_file}")
    return out_file


if __name__ == "__main__":
    fetch_and_save_companies()
