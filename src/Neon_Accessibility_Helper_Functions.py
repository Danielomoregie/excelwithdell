import os
import psycopg2
import pandas as pd
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from psycopg2 import sql

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

#-------------------------------------------------------
# Example Function (if we wanted to return a row given name of dataset and index):
# Idea is to show how to code such helper functions:

from psycopg2 import sql

def get_row_by_index(table_name, row_index, conn):
    """
    Fetch a single row ordered chronologically by date.
    """
    query = sql.SQL("""
        SELECT *
        FROM {table}
        ORDER BY date ASC
        OFFSET %s
        LIMIT 1;
    """).format(
        table=sql.Identifier(table_name)
    )

    # Convert SQL object to string
    query_str = query.as_string(conn)

    df = pd.read_sql(query_str, conn, params=(row_index,))

    return df
#-------------------------------------------------------

