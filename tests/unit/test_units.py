"""
UNIT TESTS FOR CORE PIPELINE MODULES
====================================
Runs standalone without external network calls or pre-existing data files.
"""

from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

from src.common.config import PROJECT_ROOT, RAW_DIR, STAGING_DIR, PRIMARY_DIR, CURATED_DIR
from src.rag.chunking import split_into_chunks
from src.transformation.clean_10k_to_text import ITEM_1A_PATTERN, NEXT_ITEM_PATTERN
import run


def test_config_directories():
    """Verify that all data lake directory constants are resolved properly"""
    assert PROJECT_ROOT.exists()
    for d in (RAW_DIR, STAGING_DIR, PRIMARY_DIR, CURATED_DIR):
        assert isinstance(d, Path)


def test_split_into_chunks_basic():
    """Verify word chunking logic, chunk count, and overlap"""
    sample_text = " ".join([f"word_{i}" for i in range(1000)])
    chunks = split_into_chunks(sample_text, chunk_size=500, chunk_overlap=100)

    assert len(chunks) > 1
    # First chunk has 500 words
    assert len(chunks[0].split()) == 500
    # Next chunk starts at index 400 (500 - 100 overlap)
    assert chunks[0].split()[-100:] == chunks[1].split()[:100]


def test_split_into_chunks_empty():
    """Verify empty string handling in chunking"""
    assert split_into_chunks("") == []
    assert split_into_chunks("   ") == []


def test_cik_normalization_logic():
    """Verify 10-digit zero-padding format for CIK strings"""
    sample_series = pd.Series(["320193", "123", "0000320193.0", "9999999999"])
    cleaned = sample_series.astype(str).str.split(".").str[0].str.zfill(10)

    for cik in cleaned:
        assert len(cik) == 10
        assert cik.isdigit()


def test_item_1a_regex_matching():
    """Verify Item 1A regex identifies standard and line-broken headers (e.g., MSFT case)"""
    test_cases = [
        "ITEM 1A. RISK FACTORS\nOur company faces operational risks...",
        "Item 1A.\nRisk Factors\nMarket uncertainty is significant...",
        "ITEM 1A. RIS\nK FACTORS\nTechnological disruptions affect operations...",
    ]

    for snippet in test_cases:
        match = ITEM_1A_PATTERN.search(snippet)
        assert match is not None, f"Failed to match snippet: {snippet}"


def test_run_steps_registration():
    """Verify that all 7 pipeline steps are registered in run.py with callable functions"""
    expected_steps = {"1", "2", "3", "4", "5", "6", "7"}
    assert set(run.STEPS.keys()) == expected_steps

    for step_id, (name, fn) in run.STEPS.items():
        assert isinstance(name, str)
        assert callable(fn)
