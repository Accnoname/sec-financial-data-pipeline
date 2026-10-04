"""
src/orchestration/quality_gate.py: Data Quality Gates & Validation Rules

Enforces data contracts and validation constraints before allowing execution
to transition to downstream pipeline layers.
"""

from pathlib import Path
from typing import Callable
import pandas as pd

from src.common.logger import get_logger

logger = get_logger("quality_gate")


class QualityGateFailure(Exception):
    """Raised when an artifact fails data quality validation constraints."""
    pass


class QualityGate:
    """Pre-flight and post-flight validation rules for pipeline artifacts."""

    @staticmethod
    def assert_file_exists(path: Path, min_bytes: int = 100) -> None:
        """Validates that a file exists and meets minimum size requirements."""
        if not path.exists():
            raise QualityGateFailure(f"File not found: {path}")
        size = path.stat().st_size
        if size < min_bytes:
            raise QualityGateFailure(
                f"File {path.name} is undersized ({size} bytes < {min_bytes} bytes threshold)"
            )
        logger.debug(f"[QualityGate] File passed: {path.name} ({size:,} bytes)")

    @staticmethod
    def assert_parquet_schema(
        path: Path,
        expected_columns: set[str],
        min_rows: int = 1,
        non_null_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Validates schema, row counts, and null constraints of a Parquet artifact."""
        QualityGate.assert_file_exists(path)
        df = pd.read_parquet(path)
        if len(df) < min_rows:
            raise QualityGateFailure(
                f"Parquet {path.name} has {len(df)} rows (minimum required: {min_rows})"
            )
        missing_cols = expected_columns - set(df.columns)
        if missing_cols:
            raise QualityGateFailure(
                f"Parquet {path.name} is missing mandatory columns: {missing_cols}"
            )
        if non_null_columns:
            for col in non_null_columns:
                if col in df.columns and df[col].isnull().any():
                    null_count = int(df[col].isnull().sum())
                    raise QualityGateFailure(
                        f"Parquet {path.name} contains {null_count} nulls in non-nullable column '{col}'"
                    )
        logger.debug(f"[QualityGate] Parquet schema passed: {path.name} ({len(df):,} rows)")
        return df

    @staticmethod
    def assert_markdown_filing(path: Path, min_chars: int = 10_000) -> None:
        """Validates that a Silver Item 1A markdown filing is properly extracted."""
        QualityGate.assert_file_exists(path, min_bytes=min_chars // 2)
        content = path.read_text(encoding="utf-8")
        if len(content) < min_chars:
            raise QualityGateFailure(
                f"Markdown {path.name} has {len(content)} chars (minimum required: {min_chars})"
            )
        if "Risk Factors" not in content and "RISK FACTORS" not in content:
            raise QualityGateFailure(
                f"Markdown {path.name} does not contain required 'Risk Factors' header"
            )
        logger.debug(f"[QualityGate] Markdown passed: {path.name} ({len(content):,} chars)")

    @staticmethod
    def assert_vector_collection(vector_db_path: Path, collection_name: str, min_vectors: int = 100) -> int:
        """Validates ChromaDB collection persistence and vector count threshold."""
        if not vector_db_path.exists():
            raise QualityGateFailure(f"Vector DB directory not found: {vector_db_path}")
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(
            path=str(vector_db_path),
            settings=Settings(anonymized_telemetry=False),
        )
        col = client.get_collection(collection_name)
        count = col.count()
        if count < min_vectors:
            raise QualityGateFailure(
                f"ChromaDB collection '{collection_name}' has {count} vectors (expected >= {min_vectors})"
            )
        logger.debug(f"[QualityGate] ChromaDB collection passed: '{collection_name}' ({count} vectors)")
        return count
