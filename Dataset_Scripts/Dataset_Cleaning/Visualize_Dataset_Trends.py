import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("Dataset_Scripts/CSV_Files/FusionTech Online Reviews.csv") # original dataset
#df = pd.read_csv("Dataset_Scripts/CSV_Files/FusionTech_2014_06_to_2022_06.csv")  # cleaned dataset

df["date"] = pd.to_datetime(df["timestamp"] / 1000, unit="s")
df["year_month"] = df["date"].dt.to_period("M")

monthly_counts = df.groupby("year_month").size()
monthly_counts.index = monthly_counts.index.to_timestamp()

monthly_rating = df.groupby("year_month")["rating"].mean()
monthly_rating.index = monthly_rating.index.to_timestamp()

unique_products = df.groupby("year_month")["asin"].nunique() # ASIN (Amazon Standard Identification Number)
unique_products.index = unique_products.index.to_timestamp()

plots = [
    ("Monthly Review Volume", monthly_counts),
    #("Average Rating Over Time", monthly_rating),
    #("Unique Products Reviewed Per Month", unique_products),
]

# Print CV Dynamically
print("----- Coefficient of Variation (CV) -----")

for title, data in plots:
    mean = data.mean()
    std = data.std()
    cv = std / mean if mean != 0 else 0
    print(f"{title}: {cv:.4f}")


fig, axs = plt.subplots(len(plots), 1, figsize=(12, 5 * len(plots)))

if len(plots) == 1:
    axs = [axs]

for ax, (title, data) in zip(axs, plots):
    ax.plot(data.index, data.values)
    ax.set_title(title)
    ax.set_xlabel("Month")
    ax.tick_params(axis="x", rotation=45)

plt.tight_layout()
plt.show()