from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
# Medallion Architecture Storage Layers
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
CURATED_DIR = DATA_DIR / "curated"

# Backward-compatibility aliases
RAW_DIR = BRONZE_DIR
STAGING_DIR = SILVER_DIR
PRIMARY_DIR = GOLD_DIR

for directory in (BRONZE_DIR, SILVER_DIR, GOLD_DIR, CURATED_DIR):
    directory.mkdir(parents=True, exist_ok=True)

