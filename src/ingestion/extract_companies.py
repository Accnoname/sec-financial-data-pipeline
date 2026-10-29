"""Backward-compatibility forwarder for src.bronze.extract_companies."""
from src.bronze.extract_companies import *
from src.bronze.extract_companies import fetch_and_save_companies

if __name__ == "__main__":
    fetch_and_save_companies()
