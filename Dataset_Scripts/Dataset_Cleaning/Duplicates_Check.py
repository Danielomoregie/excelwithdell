import pandas as pd
import os

input_path = "Dataset_Scripts/CSV_Files/FusionTech_2014_06_to_2022_06_Initial.csv"
output_path = "Dataset_Scripts/CSV_Files/FusionTech_2014_06_to_2022_06_deduped_Initial.csv"

df = pd.read_csv(input_path)

df["id"] = pd.to_numeric(df["id"], errors="coerce")
df = df.sort_values(by=["text", "rating", "id"])

# Find duplicates
dup_mask = df.duplicated(subset=["text", "rating"], keep=False)
duplicates = df[dup_mask].copy()

print("\n----- SAME TEXT + SAME RATING + ID Difference ≤ 1 -----")

groups = []
ids_to_remove = set()

for (text_val, rating_val), group in duplicates.groupby(["text", "rating"]):

    group = group.sort_values(by="id")
    ids = group["id"].tolist()

    close_ids = []

    for i in range(1, len(ids)):
        if abs(ids[i] - ids[i-1]) <= 1:
            close_ids.extend([ids[i-1], ids[i]])

    close_ids = sorted(set(close_ids))

    if len(close_ids) > 0:
        cluster = group[group["id"].isin(close_ids)]
        groups.append(cluster)

        # Remove all except the first ID (keep lowest ID)
        keep_id = min(close_ids)
        for val in close_ids:
            if val != keep_id:
                ids_to_remove.add(val)

total_groups = len(groups)

print(f"\nTotal duplicate clusters found: {total_groups}")

# Show up to 3 example groups
max_examples = 3

for i, cluster in enumerate(groups[:max_examples], 1):
    print(f"\n--- Example Group {i} ---")
    
    for _, row in cluster.iterrows():
        text_short = row["text"][:80].replace("\n", " ")
        print(f"ID: {int(row['id'])} | Rating: {row['rating']} | Text: {text_short}")

if total_groups > max_examples:
    remaining = total_groups - max_examples
    print(f"\n... and {remaining} more groups not shown.")

# Remove duplicates safely
original_rows = len(df)

df_cleaned = df[~df["id"].isin(ids_to_remove)].copy()

rows_removed = original_rows - len(df_cleaned)

print(f"\nRows removed from proximity duplicates: {rows_removed}")
print(f"New dataset size: {len(df_cleaned)}")

# Save new dataset (only if not exists)
if not os.path.exists(output_path):
    df_cleaned.to_csv(output_path, index=False)
    print("New deduplicated dataset saved.")
else:
    print("Deduplicated dataset already exists. No new file created.")
