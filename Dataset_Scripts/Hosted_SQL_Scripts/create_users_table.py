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

    # Enable UUID extension if not already enabled
    print("Ensuring UUID extension is enabled...")
    cur.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    conn.commit()

    # Create schema_migrations table if not exists
    print("Checking schema_migrations table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    conn.commit()
    
    # Check if this migration was already applied
    cur.execute("SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '001_create_users');")
    already_applied = cur.fetchone()[0]
    
    if already_applied:
        print("Migration 001_create_users already applied. Skipping.")
    else:
        print("Applying migration 001_create_users...")
        
        # Create departments table
        print("Creating departments table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                department_code TEXT PRIMARY KEY,
                department_name TEXT NOT NULL,
                parent_department_code TEXT NULL REFERENCES departments(department_code)
            );
        """)
        
        # Seed departments
        print("Seeding departments...")
        cur.execute("""
            INSERT INTO departments (department_code, department_name, parent_department_code)
            VALUES
                ('MARKETING', 'Marketing', NULL),
                ('SALES', 'Sales', NULL),
                ('FINANCE', 'Finance', NULL),
                ('ENGINEERING_IT', 'Engineering & IT', NULL),
                ('SUPPLY_CHAIN', 'Supply Chain / Global Operations', NULL),
                ('CUSTOMER_SUPPORT', 'Customer Support / Customer Success', NULL),
                ('SECURITY', 'Security', NULL)
            ON CONFLICT (department_code) DO NOTHING;
        """)
        
        # Create users table
        print("Creating users table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                department TEXT NOT NULL,
                sub_department TEXT,
                location TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        
        # Create indexes
        print("Creating indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_department ON users(department);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_sub_department ON users(sub_department);
        """)
        
        # Record migration
        cur.execute("""
            INSERT INTO schema_migrations (version) VALUES ('001_create_users')
            ON CONFLICT (version) DO NOTHING;
        """)
        
        conn.commit()
        print("Migration 001_create_users completed successfully.")
    
    print("Connection closed.")
    cur.close()
    conn.close()

except Exception as e:
    print("Operation failed:")
    print(e)
    if 'conn' in locals():
        conn.close()