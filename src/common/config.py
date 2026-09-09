from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "01_raw"
STAGING_DIR = DATA_DIR / "02_staging"
PRIMARY_DIR = DATA_DIR / "03_primary"
CURATED_DIR = DATA_DIR / "04_curated"

for directory in (RAW_DIR, STAGING_DIR, PRIMARY_DIR, CURATED_DIR):
    directory.mkdir(parents=True, exist_ok=True)

