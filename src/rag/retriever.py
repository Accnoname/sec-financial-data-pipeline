"""
Bước 7: RAG Query Engine - Hỏi đáp tài chính bằng Gemini API.

Nhận câu hỏi từ người dùng, tìm kiếm các chunks liên quan nhất trong ChromaDB,
sau đó gửi context cho Gemini API để tổng hợp câu trả lời có trích dẫn nguồn.
Hiển thị đầy đủ phụ lục nguồn trích dẫn và đường dẫn đối chiếu hồ sơ SEC gốc.
"""

import os
import sys
import time
import logging
import warnings
import textwrap
from dotenv import load_dotenv

# Tat toan bo canh bao va log on ao tu thu vien ben ngoai
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
for noisy_mod in ("httpx", "sentence_transformers", "huggingface_hub", "transformers", "chromadb", "google_genai", "urllib3"):
    logging.getLogger(noisy_mod).setLevel(logging.ERROR)

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from google import genai

from src.common.config import CURATED_DIR, STAGING_DIR, RAW_DIR, PROJECT_ROOT
from src.common.logger import get_logger
from src.rag.hybrid_retriever import HybridRetriever

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
        If the question is in Vietnamese, answer in fluent, professional Vietnamese while citing the sources accurately.
        If the answer cannot be determined from the sources, state that clearly.

        QUESTION:
        {question}

        SOURCE EXCERPTS:
        {context}

        ANSWER:
    """).strip()


def rag_query(
    question: str,
    ticker: str | None = None,
    year: int | None = None,
    use_hybrid: bool = True,
) -> None:
    """
    Thực hiện RAG query: tìm chunks liên quan bằng Hybrid Search (BM25 + ChromaDB RRF)
    hoặc Dense Vector Search thuần túy, sau đó gọi Gemini API để tổng hợp câu trả lời.
    In ra câu trả lời đã tổng hợp kèm Bảng phụ lục nguồn trích dẫn chi tiết.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError(
            "Chưa có GEMINI_API_KEY. Tạo file .env với nội dung:\n"
            "GEMINI_API_KEY=AIza...your_key\n"
            "Lấy key miễn phí tại: https://aistudio.google.com/apikey"
        )

    print("\n" + "=" * 70)
    print(" TRUY VẤN RAG TÀI CHÍNH (SEC FORM 10-K - V2 HYBRID SEARCH)")
    print("=" * 70)
    print(f" CÂU HỎI: {question}")
    if ticker or year:
        filters = []
        if ticker:
            filters.append(f"Ticker={ticker.upper()}")
        if year:
            filters.append(f"Year={year}")
        print(f" BỘ LỌC : {', '.join(filters)}")
    print("-" * 70)
    print(" [TIẾN ĐỘ]")

    chunks = []
    if use_hybrid:
        print(" [1/3] Đang thực hiện tìm kiếm Hybrid Search (BM25 + Dense ChromaDB RRF)...")
        hybrid_retriever = HybridRetriever(embedding_model_name=EMBEDDING_MODEL_NAME)
        chunks = hybrid_retriever.retrieve(
            query=question,
            top_k=TOP_K,
            candidate_pool_size=15,
            ticker=ticker,
            year=year,
        )
        print(f" [2/3] Đã trích xuất Top {len(chunks)} đoạn văn bản qua Reciprocal Rank Fusion (RRF):")
        for i, chunk in enumerate(chunks, start=1):
            meta = chunk["metadata"]
            d_rank = f"#{chunk['dense_rank']}" if chunk.get("dense_rank") else "N/A"
            b_rank = f"#{chunk['bm25_rank']}" if chunk.get("bm25_rank") else "N/A"
            rrf = chunk.get("rrf_score", 0.0)
            print(f"       [{i}] {meta['ticker']} ({meta['year']}) chunk #{meta['chunk_index']} | RRF={rrf:.5f} (Dense: {d_rank}, BM25: {b_rank})")
    else:
        # Fallback to pure dense vector search
        print(" [1/3] Đang tìm kiếm thuần Vector trong ChromaDB...")
        model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        query_vector = model.encode([question], show_progress_bar=False)[0].tolist()

        collection = _get_collection()
        where_filter = {}
        if ticker:
            where_filter["ticker"] = ticker.upper()
        if year:
            where_filter["year"] = int(year)

        query_kwargs = {
            "query_embeddings": [query_vector],
            "n_results": TOP_K,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = collection.query(**query_kwargs)

        print(f" [2/3] Đã trích xuất Top {TOP_K} đoạn văn bản phù hợp:")
        for i, (cid, doc, meta, dist) in enumerate(
            zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ),
            start=1,
        ):
            similarity = round(1 - dist, 4)
            print(f"       [{i}] {meta['ticker']} ({meta['year']}) chunk #{meta['chunk_index']} | similarity={similarity}")
            chunks.append({"chunk_id": cid, "text": doc, "metadata": meta, "similarity": similarity})

    # Bước 2: Gọi Gemini API kèm cơ chế tự thử lại khi quá tải
    print(f" [3/3] Đang gửi ngữ cảnh và tổng hợp câu trả lời qua Gemini AI ({GEMINI_MODEL_NAME})...")
    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(question, chunks)

    answer = None
    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
            )
            answer = response.text
            break
        except Exception as e:
            if attempt < 3:
                print(f"       -> Máy chủ tạm bận, tự động thử lại lần {attempt + 1}/3 sau {attempt * 2}s...")
                time.sleep(attempt * 2)
            else:
                raise RuntimeError(f"Không thể kết nối Gemini API sau 3 lần thử: {e}")

    # Bước 3: In câu trả lời tổng hợp bởi AI
    print("=" * 70)
    print(" KẾT QUẢ PHÂN TÍCH TỔNG HỢP (BIÊN TẬP BỞI GEMINI AI)")
    print("=" * 70)
    print(answer.strip() if answer else "Không nhận được phản hồi.")

    # Bước 4: In Bảng phụ lục nguồn trích dẫn & đường link file đối chiếu
    print("\n" + "=" * 70)
    print(" NGUỒN TRÍCH DẪN & ĐỐI CHIẾU HỒ SƠ SEC GỐC (AUDIT TRAIL)")
    print("=" * 70)
    for i, chunk in enumerate(chunks, start=1):
        meta = chunk["metadata"]
        ticker = meta["ticker"]
        year = meta["year"]
        chunk_idx = meta["chunk_index"]

        # Lay cau trich dan ngan gon
        text_clean = chunk["text"].strip().replace("\n", " ")
        text_snippet = (text_clean[:140] + "...") if len(text_clean) > 140 else text_clean

        md_path = STAGING_DIR / "sec_filings" / ticker / f"{ticker}_{year}_risk_factors.md"
        raw_dir = RAW_DIR / "sec_filings" / ticker
        raw_files = list(raw_dir.glob("*.htm*")) if raw_dir.exists() else []
        raw_path = raw_files[0] if raw_files else None

        print(f" [Source {i}] {ticker} ({year}) - Item 1A. Risk Factors (Chunk #{chunk_idx})")
        if md_path.exists():
            print(f"   - File Markdown : {md_path.relative_to(PROJECT_ROOT)}")
        if raw_path and raw_path.exists():
            print(f"   - File SEC gốc  : {raw_path.relative_to(PROJECT_ROOT)}")
        print(f"   - Trích văn bản : \"{text_snippet}\"\n")

    print("=" * 70 + "\n")
