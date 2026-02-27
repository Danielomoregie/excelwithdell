"""
Entry point to run the full ML pipeline.
Run from project root: python run_pipeline.py
"""
import sys
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from ml_pipeline.run_pipeline import run_full_pipeline

if __name__ == "__main__":
    run_full_pipeline(data_source="csv")
