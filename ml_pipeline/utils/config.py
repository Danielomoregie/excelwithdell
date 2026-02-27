"""
Configuration and constants for the Product Risk Management System.
"""
import os
from pathlib import Path

# Paths (project root is parent of ml_pipeline)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "Dataset_Scripts" / "CSV_Files"
OUTPUT_DIR = PROJECT_ROOT / "ml_pipeline" / "outputs"

# Default CSV path (cleaned dataset June 2014 - June 2022)
DEFAULT_CSV_PATH = DATA_DIR / "FusionTech_2014_06_to_2022_06_final.csv"

# Revenue assumptions
ANNUAL_REVENUE_B = 2.8
NUM_PRODUCTS = 40
RECOVERY_RATE_MIN = 0.3
RECOVERY_RATE_MAX = 0.5
MONTHS_EARLY_DETECTION = 4

# Label thresholds
PCT_1STAR_THRESHOLD = 0.35
RATING_DROP_THRESHOLD = 0.7
DEFECT_TERMS_DOUBLE = True  # defect_terms_rate doubles vs rolling baseline

# Date range (preserve temporal integrity)
START_DATE = "2014-06-01"
END_DATE = "2022-06-30"

# Train/test split
TRAIN_FRAC = 0.8  # First 80% chronological = train, last 20% = test


def ensure_output_dir():
    """Create output directory if it does not exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR
