import pandas as pd
import os

input_path = "Dataset(s)/FusionTech Online Reviews.csv"
output_path = "Dataset(s)/FusionTech_2014_06_to_2022_06.csv"

start_date = "2014-06-01"
end_date = "2022-06-30"

# Load Dataset
df = pd.read_csv(input_path)

# Convert timestamp (milliseconds → datetime)
df["date"] = pd.to_datetime(df["timestamp"] / 1000, unit="s")

original_rows = len(df)

# Filter Date Range
df_filtered = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

filtered_rows = len(df_filtered)

# Print Change Statistics
rows_removed = original_rows - filtered_rows
percent_removed = (rows_removed / original_rows) * 100

print("Original rows:", original_rows)
print("Filtered rows:", filtered_rows)
print("Rows removed:", rows_removed)
print(f"Percentage removed: {percent_removed:.2f}%")

# Save Only If File Doesn't Exist
if not os.path.exists(output_path):
    df_filtered.to_csv(output_path, index=False)
    print("Filtered dataset saved.")
else:
    print("Filtered dataset already exists. No new file created.")
