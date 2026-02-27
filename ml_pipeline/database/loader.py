"""
Data loader: loads review data from CSV or Neon SQL.
Preserves temporal integrity (June 2014 - June 2022).
"""
import pandas as pd
import os
from pathlib import Path
from ml_pipeline.utils.config import DEFAULT_CSV_PATH, START_DATE, END_DATE


def load_from_csv(csv_path: Path = None) -> pd.DataFrame:
    """
    Load cleaned dataset from CSV.
    Expects columns: rating, text, asin, user_id, timestamp, helpful_vote, brand, main_category, date
    """
    path = csv_path or DEFAULT_CSV_PATH
    if not Path(path).exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    df = pd.read_csv(path, low_memory=False)

    # Normalize column names (handle variations)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Parse timestamp / date
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    elif "timestamp" in df.columns:
        ts = pd.to_numeric(df["timestamp"], errors="coerce")
        df["date"] = pd.to_datetime(ts / 1000, unit="s", errors="coerce")

    # Drop rows with invalid date
    df = df.dropna(subset=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Optional: enforce date range (already cleaned in your pipeline)
    df = df[(df["date"] >= pd.Timestamp(START_DATE)) & (df["date"] <= pd.Timestamp(END_DATE))]

    return df


def load_from_neon(table_name: str = "fusiontech_2014_06_to_2022_06_final") -> pd.DataFrame:
    """
    Load dataset from Neon PostgreSQL using SQLAlchemy.
    Requires DATABASE_URL in .env and sqlalchemy installed.
    """
    try:
        from sqlalchemy import create_engine
        from dotenv import load_dotenv
        load_dotenv()
        url = os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL not found in .env")
        # Neon uses postgres://, SQLAlchemy may expect postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(url)
        query = f'SELECT * FROM "{table_name}"'
        df = pd.read_sql(query, engine)
        # Parse date
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        elif "timestamp" in df.columns:
            ts = pd.to_numeric(df["timestamp"], errors="coerce")
            df["date"] = pd.to_datetime(ts / 1000, unit="s", errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.sort_values("date").reset_index(drop=True)
        return df
    except ImportError:
        raise ImportError("Install sqlalchemy: pip install sqlalchemy")
    except Exception as e:
        raise RuntimeError(f"Neon load failed: {e}")


def load_data(source: str = "csv", csv_path: Path = None, table_name: str = None) -> pd.DataFrame:
    """
    Load data from CSV (default) or Neon.
    source: "csv" or "neon"
    """
    if source == "neon":
        return load_from_neon(table_name or "fusiontech_2014_06_to_2022_06_final")
    return load_from_csv(csv_path)
