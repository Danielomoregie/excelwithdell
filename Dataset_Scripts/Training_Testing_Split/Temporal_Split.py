import pandas as pd
import os

# Paths
input_path = "Dataset_Scripts/CSV_Files/FusionTech_2014_06_to_2022_06_final.csv"
output_folder = "Dataset_Scripts/Training_Testing_Split"

train_path = os.path.join(output_folder, "cleaned_train_80_percent.csv")
test_path = os.path.join(output_folder, "cleaned_test_20_percent.csv")

# Load dataset
df = pd.read_csv(input_path)

# Convert timestamp (milliseconds → datetime)
df["date"] = pd.to_datetime(df["timestamp"] / 1000, unit="s")

# Sort chronologically
df = df.sort_values("date").reset_index(drop=True)

total_reviews = len(df)

# Compute 80% split index
split_index = int(total_reviews * 0.8)

train_df = df.iloc[:split_index].copy()
test_df = df.iloc[split_index:].copy()

# Print summary
print("Total Reviews:", total_reviews)
print("Training Reviews (80%):", len(train_df))
print("Testing Reviews (20%):", len(test_df))

print("\n--- Training Period ---")
print("Start:", train_df["date"].min().date())
print("End:", train_df["date"].max().date())

print("\n--- Testing Period ---")
print("Start:", test_df["date"].min().date())
print("End:", test_df["date"].max().date())

# Create folder if needed
os.makedirs(output_folder, exist_ok=True)

# Save safely (no overwrite)
if not os.path.exists(train_path):
    train_df.to_csv(train_path, index=False)
    print("\nTraining dataset saved.")
else:
    print("\nTraining dataset already exists. Not overwritten.")

if not os.path.exists(test_path):
    test_df.to_csv(test_path, index=False)
    print("Testing dataset saved.")
else:
    print("Testing dataset already exists. Not overwritten.")
