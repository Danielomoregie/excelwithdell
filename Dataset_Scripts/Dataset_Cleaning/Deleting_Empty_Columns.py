import pandas as pd
import os

input_path = "Dataset_Scripts/CSV_Files/FusionTech_2014_06_to_2022_06_deduped_Initial.csv"
output_path = "Dataset_Scripts/CSV_Files/FusionTech_2014_06_to_2022_06_final_Initial.csv"

df = pd.read_csv(input_path)

print("Original columns:", len(df.columns))

# Identify empty columns
empty_columns = []

for col in df.columns:
    # Check if column is entirely NaN OR entirely empty strings
    if df[col].isna().all() or (df[col].astype(str).str.strip() == "").all():
        empty_columns.append(col)

# Print results
if empty_columns:
    print("\nColumns with no usable values:")
    for col in empty_columns:
        print("-", col)
else:
    print("\nNo fully empty columns found.")

# Remove empty columns safely
df_cleaned = df.drop(columns=empty_columns)

print("\nColumns after removal:", len(df_cleaned.columns))

# Save only if file doesn't exist
if not os.path.exists(output_path):
    df_cleaned.to_csv(output_path, index=False)
    print("Final cleaned dataset saved.")
else:
    print("Final dataset already exists. No new file created.")
