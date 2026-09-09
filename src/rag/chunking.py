import json
import re
from pathlib import Path
import pandas as pd

from src.common.config import STAGING_DIR, PRIMARY_DIR
from src.common.logger import get_logger

logger = get_logger("rag_chunking")


def split_into_chunks(text: str, chunk_size: int = 500, chunk_overlap: int = 100) -> list[str]:
    """Cắt văn bản thành các chunks có độ dài chunk_size từ, gối đầu chunk_overlap từ"""
    words = text.split()
    if not words:
        return []
    if len(words) <= chunk_size:
        return [" ".join(words)]
    step = chunk_size - chunk_overlap
    return [" ".join(words[i: i + chunk_size]) for i in range(0, len(words), step)]


def chunk_for_rag(ticker: str = "GOOGL", year: int | None = None) -> Path:
    """Cắt đoạn và tạo metadata cho một công ty cụ thể"""
    ticker = ticker.upper().strip()
    ticker_dir = STAGING_DIR / "sec_filings" / ticker
    if not ticker_dir.exists():
        raise FileNotFoundError(f"Chưa có thư mục {ticker_dir}. Hãy chạy Bước 4 trước.")

    md_files = list(ticker_dir.glob("*_risk_factors.md"))
    if not md_files:
        raise FileNotFoundError(f"Chưa có file Markdown tại {ticker_dir}. Hãy chạy Bước 4 trước.")

    md_file = md_files[0]
    if year is None:
        m = re.search(r"(\d{4})", md_file.name)
        year = int(m.group(1)) if m else 2025

    content = md_file.read_text(encoding="utf-8")
    raw_chunks = split_into_chunks(content)

    records = [
        {
            "chunk_id": f"{ticker}_{year}_RF_{idx:04d}",
            "ticker": ticker,
            "year": year,
            "section": "Item 1A. Risk Factors",
            "chunk_index": idx,
            "total_chunks": len(raw_chunks),
            "word_count": len(text.split()),
            "text": text
        }
        for idx, text in enumerate(raw_chunks, start=1)
    ]

    out_dir = PRIMARY_DIR / "chunks"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_parquet = out_dir / f"{ticker}_{year}_chunks.parquet"
    out_json = out_dir / f"{ticker}_{year}_chunks.json"

    df = pd.DataFrame(records)
    df.to_parquet(out_parquet, index=False, engine="pyarrow", compression="snappy")
    out_json.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"[{ticker}] Đã tạo {len(records)} chunks -> {out_parquet.name}")
    return out_parquet


def chunk_all_risk_factors() -> list[Path]:
    """Cắt đoạn cho toàn bộ công ty có trong Tầng Silver (02_staging) và tạo all_chunks.parquet"""
    staging_filings = STAGING_DIR / "sec_filings"
    if not staging_filings.exists():
        raise FileNotFoundError(f"Chưa có dữ liệu tại {staging_filings}. Hãy chạy Bước 4 trước.")

    md_files = sorted(staging_filings.glob("*/*_risk_factors.md"))
    if not md_files:
        raise FileNotFoundError("Không tìm thấy file Markdown nào để chunking.")

    all_records = []
    generated_files = []
    logger.info(f"Bắt đầu Semantic Chunking cho {len(md_files)} file Markdown...")

    for md_path in md_files:
        ticker = md_path.parent.name
        m = re.search(r"(\d{4})", md_path.name)
        year = int(m.group(1)) if m else 2025

        content = md_path.read_text(encoding="utf-8")
        raw_chunks = split_into_chunks(content)

        records = [
            {
                "chunk_id": f"{ticker}_{year}_RF_{idx:04d}",
                "ticker": ticker,
                "year": year,
                "section": "Item 1A. Risk Factors",
                "chunk_index": idx,
                "total_chunks": len(raw_chunks),
                "word_count": len(text.split()),
                "text": text
            }
            for idx, text in enumerate(raw_chunks, start=1)
        ]

        out_dir = PRIMARY_DIR / "chunks"
        out_dir.mkdir(parents=True, exist_ok=True)

        out_parquet = out_dir / f"{ticker}_{year}_chunks.parquet"
        out_json = out_dir / f"{ticker}_{year}_chunks.json"

        df = pd.DataFrame(records)
        df.to_parquet(out_parquet, index=False, engine="pyarrow", compression="snappy")
        out_json.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

        generated_files.append(out_parquet)
        all_records.extend(records)
        logger.info(f"[{ticker}] Đã tạo {len(records)} chunks ({out_parquet.name})")

    # Tạo bảng tổng hợp all_chunks.parquet trong Tầng Gold
    unified_df = pd.DataFrame(all_records)
    unified_parquet = PRIMARY_DIR / "chunks" / "all_chunks.parquet"
    unified_json = PRIMARY_DIR / "chunks" / "all_chunks.json"

    unified_df.to_parquet(unified_parquet, index=False, engine="pyarrow", compression="snappy")
    unified_json.write_text(json.dumps(all_records, ensure_ascii=False, indent=2), encoding="utf-8")
    generated_files.append(unified_parquet)

    logger.info(
        f"Hoàn thành Tầng Gold: Đã tổng hợp {len(all_records)} chunks từ {len(md_files)} công ty -> {unified_parquet.name}"
    )
    return generated_files


if __name__ == "__main__":
    chunk_all_risk_factors()
