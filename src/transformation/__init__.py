"""Backward-compatibility forwarder for src.silver."""
from src.silver import (
    clean_companies,
    clean_10k_to_text,
    extract_risk_factors,
    extract_all_risk_factors,
    get_filing_year,
    ITEM_1A_PATTERN,
    NEXT_ITEM_PATTERN,
)

__all__ = [
    "clean_companies",
    "clean_10k_to_text",
    "extract_risk_factors",
    "extract_all_risk_factors",
    "get_filing_year",
    "ITEM_1A_PATTERN",
    "NEXT_ITEM_PATTERN",
]
