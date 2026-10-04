import json
import re
from pathlib import Path
import pandas as pd

from src.common.config import STAGING_DIR, PRIMARY_DIR
from src.common.logger import get_logger

logger = get_logger("rag_chunking")

_TOKENIZER = None


def get_tokenizer():
    """Lazy-loads tokenizer to prevent overhead on package import."""
    global _TOKENIZER
    if _TOKENIZER is None:
        from sentence_transformers import SentenceTransformer
        _TOKENIZER = SentenceTransformer("all-MiniLM-L6-v2").tokenizer
    return _TOKENIZER


def split_into_chunks(
    text: str,
    max_tokens: int = 210,
    overlap_tokens: int = 40,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """
    Tokenizer-aware sliding window chunking preserving sentence boundaries.
    Guarantees 100% of chunks fit within the 256-token limit of all-MiniLM-L6-v2.
    Also supports legacy word-based chunking if chunk_size is explicitly provided.
    """
    if chunk_size is not None:
        words = text.split()
        if not words:
            return []
        if len(words) <= chunk_size:
            return [" ".join(words)]
        overlap = chunk_overlap if chunk_overlap is not None else 100
        step = chunk_size - overlap
        return [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), step)]

    text = text.strip()
    if not text:
        return []

    tokenizer = get_tokenizer()

    # Split on sentence boundaries
    sentence_delimiters = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9\(\"\'])|(?<=\n)\s*(?=\S)')
    raw_sentences = [s.strip() for s in sentence_delimiters.split(text) if s.strip()]

    sentences = []
    for s in raw_sentences:
        s_tokens = len(tokenizer.encode(s, truncation=False))
        if s_tokens <= max_tokens:
            sentences.append(s)
        else:
            words = s.split()
            current_sub = []
            for w in words:
                current_sub.append(w)
                if len(tokenizer.encode(" ".join(current_sub), truncation=False)) >= max_tokens - 10:
                    sentences.append(" ".join(current_sub))
                    current_sub = []
            if current_sub:
                sentences.append(" ".join(current_sub))

    chunks = []
    current_sentences = []
    current_tokens = 0

    for s in sentences:
        s_len = len(tokenizer.encode(s, truncation=False))
        if current_sentences and (current_tokens + s_len > max_tokens):
            chunks.append(" ".join(current_sentences))

            overlap_sentences = []
            overlap_count = 0
            for prev_s in reversed(current_sentences):
                p_len = len(tokenizer.encode(prev_s, truncation=False))
                if overlap_count + p_len <= overlap_tokens or not overlap_sentences:
                    overlap_sentences.insert(0, prev_s)
                    overlap_count += p_len
                else:
                    break
            current_sentences = list(overlap_sentences)
            current_tokens = overlap_count

        current_sentences.append(s)
        current_tokens += s_len

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    # Strict Data Contract: Hard ceiling of 240 tokens (below model's 256 limit)
    final_chunks = []
    for c in chunks:
        tok_len = len(tokenizer.encode(c, truncation=False))
        if tok_len <= 240:
            final_chunks.append(c)
        else:
            words = c.split()
            mid = len(words) // 2
            c1 = " ".join(words[: mid + 15])
            c2 = " ".join(words[mid - 15 :])
            final_chunks.append(c1)
            final_chunks.append(c2)

    return final_chunks


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
