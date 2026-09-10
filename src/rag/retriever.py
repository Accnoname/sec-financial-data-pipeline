"""
Bước 7: RAG Query Engine - Hỏi đáp tài chính bằng Gemini API.

Nhận câu hỏi từ người dùng, tìm kiếm các chunks liên quan nhất trong ChromaDB,
sau đó gửi context cho Gemini API để tổng hợp câu trả lời có trích dẫn nguồn.
"""

import os
import textwrap
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from google import genai
from dotenv import load_dotenv

from src.common.config import CURATED_DIR, PROJECT_ROOT
from src.common.logger import get_logger

load_dotenv(PROJECT_ROOT / ".env")

logger = get_logger("rag_retriever")

COLLECTION_NAME = "sec_risk_factors"
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
TOP_K = 5


def _get_collection() -> chromadb.Collection:
    """Kết nối đến ChromaDB và lấy collection."""
    vector_db_path = CURATED_DIR / "vector_db"
    if not vector_db_path.exists():
        raise FileNotFoundError(
            f"Chưa có vector index tại '{vector_db_path}'. "
            "Hãy chạy Bước 6 trước: python run.py 6"
        )
    client = chromadb.PersistentClient(
        path=str(vector_db_path),
        settings=Settings(anonymized_telemetry=False),
    )
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        raise RuntimeError(
            f"Collection '{COLLECTION_NAME}' chưa tồn tại. "
            "Hãy chạy Bước 6 trước: python run.py 6"
        )


def _build_prompt(question: str, chunks: list[dict]) -> str:
    """Xây dựng prompt gửi cho Gemini từ câu hỏi và các chunks ngữ cảnh."""
    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        meta = chunk["metadata"]
        source = f"[Source {i}: {meta['ticker']} {meta['year']}, {meta['section']}, chunk {meta['chunk_index']}]"
        context_parts.append(f"{source}\n{chunk['text']}")

    context = "\n\n---\n\n".join(context_parts)

    return textwrap.dedent(f"""
        You are a financial risk analyst specializing in SEC 10-K filings.
        Answer the following question based ONLY on the provided source excerpts.
        Always cite your sources using the [Source N] labels.
        If the answer cannot be determined from the sources, state that clearly.

        QUESTION:
        {question}

        SOURCE EXCERPTS:
        {context}

        ANSWER:
    """).strip()


def rag_query(question: str) -> None:
    """
    Thực hiện RAG query: tìm chunks liên quan và gọi Gemini API để trả lời.

    Args:
        question: Câu hỏi về rủi ro tài chính bằng tiếng Anh hoặc tiếng Việt.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError(
            "Chưa có GEMINI_API_KEY. Tạo file .env với nội dung:\n"
            "GEMINI_API_KEY=AIza...your_key\n"
            "Lấy key miễn phí tại: https://aistudio.google.com/apikey"
        )

    logger.info(f'Câu hỏi: "{question}"')

    # Bước 1: Tạo embedding cho câu hỏi
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    query_vector = model.encode([question])[0].tolist()

    # Bước 2: Tìm kiếm chunks liên quan trong ChromaDB
    collection = _get_collection()
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    print("\n" + "=" * 70)
    print(f"CÂU HỎI: {question}")
    print("=" * 70)
    print(f"\nTop {TOP_K} chunks liên quan nhất:")

    for i, (doc, meta, dist) in enumerate(
        zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ),
        start=1,
    ):
        similarity = round(1 - dist, 4)
        print(
            f"  [{i}] {meta['ticker']} {meta['year']} "
            f"chunk #{meta['chunk_index']} | similarity={similarity}"
        )
        chunks.append({"text": doc, "metadata": meta})

    # Bước 3: Gọi Gemini API
    client = genai.Client(api_key=api_key)

    prompt = _build_prompt(question, chunks)
    logger.info(f"Đang gọi Gemini ({GEMINI_MODEL_NAME})...")

    response = client.models.generate_content(
        model=GEMINI_MODEL_NAME,
        contents=prompt,
    )
    answer = response.text

    print("\n" + "-" * 70)
    print("CÂU TRẢ LỜI (tổng hợp bởi Gemini):")
    print("-" * 70)
    print(answer)
    print("=" * 70 + "\n")
