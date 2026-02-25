import os
import psycopg2
import pandas as pd
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# ==============================
# CONNECTION MANAGEMENT
# ==============================

def get_connection():
    """Create and return a Neon PostgreSQL connection."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL not found in .env")

    print("Connected to Neon Hosted Server!\n")
    return psycopg2.connect(database_url)


def close_connection(conn):
    """Safely close database connection."""
    if conn:
        print("\nThank you for being responsible! :)")
        conn.close()

