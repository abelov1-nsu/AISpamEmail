import pandas as pd
from ..src.config import PATHS

df = pd.read_csv(PATHS.processed_dataset_clean)
print("Всего:", len(df))
print(df["label"].value_counts())
print("\nСредние длины body:")
print(df.groupby("label")["body"].apply(lambda x: int(x.str.len().mean())))
print("\nМаксимальные длины:")
print(df.groupby("label")["body"].apply(lambda x: int(x.str.len().max())))
print("\nHTML в body:")
print(df.groupby("label")["body"].apply(lambda x: (x.str.contains("<", regex=False)).mean()))
print("\nLowercase-ratio:")
print(df.groupby("label")["body"].apply(lambda x: x.apply(lambda t: t == t.lower()).mean()))
