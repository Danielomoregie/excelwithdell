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
    print("Connecting to Neon database...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Check if this migration was already applied
    cur.execute("SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '002_add_password');")
    already_applied = cur.fetchone()[0]
    
    if already_applied:
        print("Migration 002_add_password already applied. Skipping.")
    else:
        print("Applying migration 002_add_password...")
        
        # Add password_hash column to users table
        print("Adding password_hash column to users table...")
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS password_hash TEXT;
        """)
        
        # Record migration
        cur.execute("""
            INSERT INTO schema_migrations (version) VALUES ('002_add_password')
            ON CONFLICT (version) DO NOTHING;
        """)
        
        conn.commit()
        print("Migration 002_add_password completed successfully.")
    
    print("Connection closed.")
    cur.close()
    conn.close()

except Exception as e:
    print("Operation failed:")
    print(e)
    if 'conn' in locals():
        conn.close()
