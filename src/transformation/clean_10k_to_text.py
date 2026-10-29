"""Backward-compatibility forwarder for src.silver.clean_10k_to_text."""
from src.silver.clean_10k_to_text import *
from src.silver.clean_10k_to_text import (
    clean_10k_to_text,
    extract_risk_factors,
    extract_all_risk_factors,
    get_filing_year,
    ITEM_1A_PATTERN,
    NEXT_ITEM_PATTERN,
)

if __name__ == "__main__":
    extract_all_risk_factors()
