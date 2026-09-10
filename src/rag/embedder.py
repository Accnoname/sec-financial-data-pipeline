"""
Bước 6: Tạo vector embedding và nạp vào ChromaDB.

Đọc all_chunks.parquet từ tầng Gold, dùng sentence-transformers để tạo vector
embedding cho từng chunk, sau đó lưu vào ChromaDB tại data/04_curated/vector_db/.
"""

import os
import pandas as pd
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from src.common.config import PRIMARY_DIR, CURATED_DIR
from src.common.logger import get_logger

logger = get_logger("rag_embedder")

COLLECTION_NAME = "sec_risk_factors"
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


def build_vector_index() -> None:
    """
    Đọc all_chunks.parquet, tạo embedding cho mỗi chunk và nạp vào ChromaDB.
    Nếu collection đã tồn tại, xóa và tạo lại để đảm bảo tính nhất quán.
    """
    chunks_path = PRIMARY_DIR / "chunks" / "all_chunks.parquet"
    if not chunks_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {chunks_path}. Hãy chạy Bước 5 trước: python run.py 5"
        )

    logger.info(f"Đang đọc chunks từ {chunks_path.name}...")
    df = pd.read_parquet(chunks_path, engine="pyarrow")
    logger.info(f"Đã nạp {len(df)} chunks từ {df['ticker'].nunique()} công ty.")

    # Khởi tạo ChromaDB lưu trên đĩa
    vector_db_path = CURATED_DIR / "vector_db"
    vector_db_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(vector_db_path),
        settings=Settings(anonymized_telemetry=False),
    )

    # Xóa collection cũ nếu đã tồn tại để tạo lại từ đầu
    existing = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)
        logger.info(f"Đã xóa collection cũ '{COLLECTION_NAME}'.")

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Tải mô hình embedding (tự động tải về lần đầu, ~80MB)
    logger.info(f"Đang tải mô hình embedding '{EMBEDDING_MODEL_NAME}'...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    texts = df["text"].tolist()
    ids = df["chunk_id"].tolist()
    metadatas = df[["ticker", "year", "section", "chunk_index", "word_count"]].to_dict(
        orient="records"
    )
    # ChromaDB metadata không chấp nhận int64 của numpy, cần chuyển sang Python int
    for meta in metadatas:
        meta["year"] = int(meta["year"])
        meta["chunk_index"] = int(meta["chunk_index"])
        meta["word_count"] = int(meta["word_count"])

    logger.info(f"Đang tạo embedding cho {len(texts)} chunks (có thể mất 1-2 phút)...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)

    # Nạp theo lô 100 để tránh vấn đề bộ nhớ
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        collection.add(
            ids=ids[i : i + batch_size],
            embeddings=embeddings[i : i + batch_size].tolist(),
            documents=texts[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
        )

    logger.info(
        f"Hoàn thành Bước 6: Đã nạp {len(texts)} chunks vào ChromaDB "
        f"tại '{vector_db_path}'."
    )
    logger.info(
        "Bước tiếp theo: python run.py 7 \"What are Nvidia's AI risks in 2026?\""
    )
