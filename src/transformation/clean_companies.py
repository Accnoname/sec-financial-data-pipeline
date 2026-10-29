"""Backward-compatibility forwarder for src.silver.clean_companies."""
from src.silver.clean_companies import *
from src.silver.clean_companies import clean_companies

if __name__ == "__main__":
    clean_companies()
