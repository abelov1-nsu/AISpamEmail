import pandas as pd

df = pd.read_csv("data/dataset.csv")

print("Всего:", len(df))
print(df["label"].value_counts())
print("\n--- Длины body ---")
print(df.groupby("label")["body"].apply(lambda x: int(x.str.len().mean())))
print(df.groupby("label")["body"].apply(lambda x: int(x.str.len().max())))

print("\n--- HTML-мусор ---")
for label in df["label"].unique():
    sub = df[df["label"] == label]
    print(f"{label}: {(sub['body'].str.contains('<', regex=False)).mean():.0%}")

print("\n--- Lowercase-мусор ---")
for label in df["label"].unique():
    sub = df[df["label"] == label]
    ratio = sub["body"].apply(lambda t: t == t.lower()).mean()
    print(f"{label}: {ratio:.0%} полностью lowercase")