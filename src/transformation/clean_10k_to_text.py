import json
import re
import warnings
from pathlib import Path
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from src.common.config import RAW_DIR, STAGING_DIR
from src.common.logger import get_logger

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
logger = get_logger("clean_10k_to_text")

# Regex nhận diện tiêu đề Item 1A (hỗ trợ cả trường hợp bị ngắt dòng như MSFT: RIS\nK FACTORS)
ITEM_1A_PATTERN = re.compile(
    r"(?:^|\n)ITEM[\s\xa0]*1A\.?[\s\xa0\n]*(?:RISK|RIS[\s\xa0\n]*K)?[\s\xa0\n]*FACTORS",
    re.I
)
NEXT_ITEM_PATTERN = re.compile(r"\nITEM[\s\xa0]*(?:1B|1C|2)\.?", re.I)


def get_filing_year(ticker: str, ticker_dir: Path, htm_file: Path) -> int:
    """Tự động suy luận năm tài chính từ metadata hoặc tên file"""
    meta_file = ticker_dir / "metadata.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            filing_date = meta.get("filing_date", "")
            if filing_date and len(filing_date) >= 4:
                # Nếu nộp đầu năm (tháng 1, 2) thì thường là niên độ năm trước, trừ khi tên file chỉ rõ
                doc_name = meta.get("document", "")
                m = re.search(r"(\d{4})\d{4}\.htm", doc_name)
                if m:
                    return int(m.group(1))
                return int(filing_date[:4])
        except Exception:
            pass

    # Thử bóc từ tên file HTML (vd: aapl-20250927.htm -> 2025)
    match = re.search(r"(\d{4})\d{4}\.htm", htm_file.name)
    if match:
        return int(match.group(1))

    match_year = re.search(r"202\d", htm_file.name)
    if match_year:
        return int(match_year.group(0))

    return 2025


def extract_risk_factors(ticker: str = "GOOGL", year: int | None = None) -> Path:
    ticker = ticker.upper().strip()
    ticker_dir = RAW_DIR / "sec_filings" / ticker
    htm_files = list(ticker_dir.glob("*.htm*")) if ticker_dir.exists() else []
    if not htm_files:
        raise FileNotFoundError(f"Không tìm thấy file HTML cho {ticker} tại {ticker_dir}")

    raw_html_path = htm_files[0]
    if year is None:
        year = get_filing_year(ticker, ticker_dir, raw_html_path)

    logger.info(f"[{ticker}] Đang bóc tách HTML: {raw_html_path.name} (Năm: {year})")
    html_content = raw_html_path.read_text(encoding="utf-8", errors="ignore")

    soup = BeautifulSoup(html_content, "lxml")
    for tag in soup(["script", "style", "ix:header"]):
        tag.decompose()

    raw_text = soup.get_text(separator="\n")
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    full_text = "\n".join(lines)

    matches = list(ITEM_1A_PATTERN.finditer(full_text))
    risk_factors_text = ""

    for m in matches:
        start = m.start()
        end_m = NEXT_ITEM_PATTERN.search(full_text[start + 20:])
        if end_m:
            candidate = full_text[start: start + 20 + end_m.start()].strip()
            if len(candidate) > 5000:
                risk_factors_text = candidate
                break

    if not risk_factors_text:
        logger.warning(f"[{ticker}] Không khớp chính xác Item 1A > 5000 chars. Dùng fallback 50.000 ký tự đầu.")
        risk_factors_text = full_text[:50000]

    out_dir = STAGING_DIR / "sec_filings" / ticker
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{ticker}_{year}_risk_factors.md"
    out_file.write_text(
        f"# 📊 {ticker} - {year} Form 10-K: Item 1A. Risk Factors\n\n{risk_factors_text}",
        encoding="utf-8"
    )

    logger.info(f"[{ticker}] Đã xuất Markdown: {out_file.name} ({len(risk_factors_text)/1024:,.1f} KB)")
    return out_file


def extract_all_risk_factors(tickers: list[str] | None = None) -> list[Path]:
    """Bóc tách Risk Factors cho tất cả các mã công ty có trong data/01_raw/sec_filings/"""
    filings_root = RAW_DIR / "sec_filings"
    if not filings_root.exists():
        raise FileNotFoundError(f"Chưa có dữ liệu thô tại {filings_root}. Hãy chạy Bước 3 trước.")

    if tickers:
        target_dirs = [filings_root / t.upper() for t in tickers]
    else:
        target_dirs = [d for d in sorted(filings_root.iterdir()) if d.is_dir()]

    results = []
    logger.info(f"Bắt đầu bóc tách Item 1A cho {len(target_dirs)} công ty...")
    for tdir in target_dirs:
        ticker = tdir.name
        try:
            out_path = extract_risk_factors(ticker)
            results.append(out_path)
        except Exception as e:
            logger.error(f"[{ticker}] Lỗi bóc tách: {e}")

    logger.info(f"Hoàn thành bóc tách {len(results)}/{len(target_dirs)} công ty sang Tầng Silver Markdown.")
    return results


if __name__ == "__main__":
    extract_all_risk_factors()
