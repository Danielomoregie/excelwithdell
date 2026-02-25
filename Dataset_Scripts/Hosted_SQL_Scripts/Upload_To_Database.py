# PLEASE DO NOT RUN THIS CODE, IT WILL DRAIN COMPUTE USAGE!

import os
import psycopg2
import pandas as pd
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# LOAD ENV
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("DATABASE_URL not found in .env file.")
    exit()

# FIND ALL CSV FILES IN REPO
PROJECT_ROOT = os.getcwd()
csv_files = []

for root, dirs, files in os.walk(PROJECT_ROOT):
    for file in files:
        if file.endswith(".csv"):
            full_path = os.path.join(root, file)
            csv_files.append(full_path)

if not csv_files:
    print("No CSV files found in repository.")
    exit()

print("\nCSV files found:")
for i, path in enumerate(csv_files):
    print(f"{i+1}. {os.path.relpath(path, PROJECT_ROOT)}")

# USER SELECTS FILE
choice = int(input("\nSelect file number to upload: "))
csv_path = csv_files[choice - 1]
selected_file = os.path.basename(csv_path)

# CREATE SAFE TABLE NAME
table_name = (
    os.path.splitext(selected_file)[0]
    .lower()
    .replace(" ", "_")
    .replace("-", "_")
)

print(f"\nTarget table name: {table_name}")

# CONNECT TO NEON
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# CHECK IF TABLE EXISTS
cur.execute("""
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public'
    AND table_name = %s
);
""", (table_name,))

exists = cur.fetchone()[0]

if exists:
    print(f"\nTable '{table_name}' already exists. No upload performed.")
    cur.close()
    conn.close()
    exit()

# READ CSV
df = pd.read_csv(csv_path)

if df.empty:
    print("CSV file is empty. No upload performed.")
    cur.close()
    conn.close()
    exit()

# Clean column names
df.columns = [
    col.strip().lower().replace(" ", "_").replace("-", "_")
    for col in df.columns
]

# ASK USER FOR COLUMN DATATYPES
allowed_types = [
    "TEXT",
    "INTEGER",
    "BIGINT",
    "FLOAT",
    "BOOLEAN",
    "TIMESTAMP",
    "DATE"
]

print("\nAvailable Datatypes:\n")
for i, dtype in enumerate(allowed_types):
    print(f"{i + 1}. {dtype}")

print("\nChoose datatype for each column:\n")

column_types = {}

for col in df.columns:
    while True:
        try:
            choice = int(input(f"{col} → Enter datatype number: "))
            if 1 <= choice <= len(allowed_types):
                column_types[col] = allowed_types[choice - 1]
                break
            else:
                print("Invalid selection. Try again.")
        except ValueError:
            print("Please enter a valid number.")

# CREATE TABLE WITH CHOSEN TYPES
columns_sql = ", ".join(
    [f'"{col}" {column_types[col]}' for col in df.columns]
)

cur.execute(f"""
CREATE TABLE {table_name} (
    {columns_sql}
);
""")

# BULK INSERT
insert_query = f"""
INSERT INTO {table_name} ({', '.join(df.columns)})
VALUES %s
"""

execute_values(cur, insert_query, df.astype(str).values.tolist())

conn.commit()

print(f"\nTable '{table_name}' created successfully.")
print(f"Rows inserted: {len(df)}")

cur.close()
conn.close()