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

# CSV PATH
csv_path = "Dataset_Scripts/CSV_Files/FusionTech Online Reviews_Initial.csv"

if not os.path.exists(csv_path):
    print(f"CSV file not found at: {csv_path}")
    exit()

# TABLE NAME
table_name = "online_reviews"

print(f"Uploading: {csv_path}")
print(f"Target table: {table_name}")

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
    print(f"\nTable '{table_name}' already exists. Dropping and re-creating...")
    cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
    conn.commit()

# READ CSV
print("\nReading CSV file...")
df = pd.read_csv(csv_path)

if df.empty:
    print("CSV file is empty. No upload performed.")
    cur.close()
    conn.close()
    exit()

print(f"Loaded {len(df)} rows")

# Clean column names
df.columns = [
    col.strip().lower().replace(" ", "_").replace("-", "_")
    for col in df.columns
]

print(f"Columns: {', '.join(df.columns)}")

# AUTO-DETECT COLUMN TYPES
print("\nAuto-detecting column types...")
column_types = {}

for col in df.columns:
    # Try to infer type from data
    non_null = df[col].dropna()
    
    if non_null.empty:
        column_types[col] = "TEXT"
    elif col in ["timestamp"]:
        column_types[col] = "BIGINT"
    elif pd.api.types.is_integer_dtype(df[col]):
        column_types[col] = "INTEGER"
    elif pd.api.types.is_float_dtype(df[col]):
        column_types[col] = "FLOAT"
    elif pd.api.types.is_bool_dtype(df[col]):
        column_types[col] = "BOOLEAN"
    else:
        column_types[col] = "TEXT"
    
    print(f"  {col}: {column_types[col]}")

# CREATE TABLE WITH DETECTED TYPES
columns_sql = ", ".join(
    [f'"{col}" {column_types[col]}' for col in df.columns]
)

print(f"\nCreating table '{table_name}'...")
cur.execute(f"""
CREATE TABLE {table_name} (
    {columns_sql}
);
""")

# BULK INSERT - WITH TYPE CONVERSION
print("Inserting data...")

# Convert data with proper type handling
data_to_insert = []
for _, row in df.iterrows():
    converted_row = []
    for col, val in row.items():
        if pd.isna(val) or val == 'nan':
            converted_row.append(None)
        elif column_types[col] == "INTEGER":
            try:
                converted_row.append(int(float(val)))
            except:
                converted_row.append(None)
        elif column_types[col] == "BIGINT":
            try:
                converted_row.append(int(float(val)))
            except:
                converted_row.append(None)
        elif column_types[col] == "FLOAT":
            try:
                converted_row.append(float(val))
            except:
                converted_row.append(None)
        else:
            converted_row.append(str(val))
    data_to_insert.append(tuple(converted_row))

insert_query = f"""
INSERT INTO {table_name} ({', '.join([f'"{col}"' for col in df.columns])})
VALUES %s
"""

execute_values(cur, insert_query, data_to_insert)

conn.commit()

print(f"\n✅ Table '{table_name}' created successfully.")
print(f"✅ Rows inserted: {len(df)}")

cur.close()
conn.close()
