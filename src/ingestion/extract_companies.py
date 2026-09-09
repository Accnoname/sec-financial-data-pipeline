import json
from pathlib import Path
import requests

from src.common.config import RAW_DIR
from src.common.logger import get_logger

logger = get_logger("extract_companies")
SEC_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
HEADERS = {"User-Agent": "StockMarketRAGDataEngineer student@university.edu.vn"}


def fetch_and_save_companies() -> Path:
    logger.info(f"Đang tải danh sách công ty từ SEC.gov: {SEC_URL}")
    resp = requests.get(SEC_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    payload = resp.json()
    fields, rows = payload["fields"], payload["data"]
    companies = [dict(zip(fields, row)) for row in rows]

    out_file = RAW_DIR / "companies" / "all_companies.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(companies, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"Đã lưu {len(companies):,} công ty vào {out_file}")
    return out_file


if __name__ == "__main__":
    fetch_and_save_companies()

