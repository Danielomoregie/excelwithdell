import pandas as pd

# Load file
df = pd.read_csv("Dataset_Scripts/CSV_Files/FusionTech Online Reviews_Initial.csv")

# Missing Value Statistics
missing_count = df.isnull().sum()
missing_percent = (df.isnull().mean() * 100)

missing_stats = pd.DataFrame({
    "Missing_Count": missing_count,
    "Missing_Percent": missing_percent.round(2)
}).sort_values(by="Missing_Percent", ascending=False)

print("=== Missing Value Statistics ===")
print(missing_stats)