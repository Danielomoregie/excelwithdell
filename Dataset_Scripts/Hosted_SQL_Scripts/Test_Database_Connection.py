import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("DATABASE_URL not found. Check your .env file.")
    exit()

try:
    # Connect to Neon PostgreSQL
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Simple test query
    cur.execute("SELECT NOW();")
    result = cur.fetchone()

    print("Connected successfully.")
    print("Server time:", result)

    cur.close()
    conn.close()

except Exception as e:
    print("Connection failed:")
    print(e)